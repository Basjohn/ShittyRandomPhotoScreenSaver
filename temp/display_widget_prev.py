"""
Display widget for showing images fullscreen.

Handles image display, input events, and error messages.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QKeyEvent, QMouseEvent, QPaintEvent, QFont
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor
from rendering.pan_and_scan import PanAndScan
from transitions.base_transition import BaseTransition
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from core.logging.logger import get_logger
from transitions.gl_crossfade_transition import _GLFadeWidget
from transitions.overlay_manager import hide_all_overlays, any_overlay_ready_for_display

logger = get_logger(__name__)


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
    
    def __init__(self, screen_index: int = 0, 
                 display_mode: DisplayMode = DisplayMode.FILL,
                 settings_manager=None,
                 parent: Optional[QWidget] = None):
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
        self.weather_widget: Optional[WeatherWidget] = None
        self._current_transition: Optional[BaseTransition] = None
        self._image_label: Optional[QLabel] = None  # For pan and scan
        self._pan_and_scan = PanAndScan(self)
        self._screen = None  # Store screen reference for DPI
        self._device_pixel_ratio = 1.0  # DPI scaling factor
        self._initial_mouse_pos = None  # Track mouse movement for exit
        self._mouse_move_threshold = 10  # Pixels of movement before exit
        self._target_fps = 60  # Target FPS derived from screen refresh rate
        
        # FIX: Use ResourceManager for Qt object lifecycle
        try:
            from core.resources.manager import ResourceManager
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
        self.showFullScreen()
        # Configure per-display refresh rate and animation cadence (does not touch prewarm)
        try:
            self._configure_refresh_rate_sync()
        except Exception as e:
            logger.warning(f"Failed to configure refresh rate sync: {e}")
        # Reconfigure when screen changes
        try:
            handle = self.windowHandle()
            if handle is not None:
                handle.screenChanged.connect(lambda s: self._configure_refresh_rate_sync())
        except Exception:
            pass
        
        # Pre-warm GL contexts if hardware acceleration enabled
        if self.settings_manager:
            hw_accel = self.settings_manager.get('display.hw_accel', False)
            # Handle string boolean values from settings file
            if isinstance(hw_accel, str):
                hw_accel = hw_accel.lower() in ('true', '1', 'yes')
            if hw_accel:
                self._prewarm_gl_contexts()
        
        # Setup overlay widgets AFTER geometry is set
        if self.settings_manager:
            self._setup_widgets()

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
    
    def _setup_widgets(self) -> None:
        """Setup overlay widgets (clock, weather) based on settings."""
        if not self.settings_manager:
            logger.warning("No settings_manager provided - widgets will not be created")
            return
        
        logger.debug(f"Setting up overlay widgets for screen {self.screen_index}")
        
        # Clock widget - get widgets dict, then clock sub-dict
        widgets = self.settings_manager.get('widgets', {})
        clock_settings = widgets.get('clock', {}) if isinstance(widgets, dict) else {}
        logger.debug(f"Widgets config: {widgets}")
        logger.debug(f"Clock settings retrieved: {clock_settings}")
        # Normalize booleans possibly stored as strings
        def _to_bool(val, default=False):
            if isinstance(val, str):
                return val.lower() in ('true', '1', 'yes')
            return bool(val) if val is not None else default
        clock_enabled = _to_bool(clock_settings.get('enabled', False), False)
        if clock_enabled:
            # Parse settings
            time_format = TimeFormat.TWELVE_HOUR if clock_settings.get('format', '12h') == '12h' else TimeFormat.TWENTY_FOUR_HOUR
            position_str = clock_settings.get('position', 'Top Right')
            show_seconds = _to_bool(clock_settings.get('show_seconds', False), False)
            timezone_str = clock_settings.get('timezone', 'local')
            show_timezone = _to_bool(clock_settings.get('show_timezone', False), False)
            font_size = clock_settings.get('font_size', 48)
            margin = clock_settings.get('margin', 20)
            color = clock_settings.get('color', [255, 255, 255, 230])
            
            # Map position string to enum
            position_map = {
                'Top Left': ClockPosition.TOP_LEFT,
                'Top Right': ClockPosition.TOP_RIGHT,
                'Top Center': ClockPosition.TOP_CENTER,
                'Center': ClockPosition.CENTER,
                'Bottom Left': ClockPosition.BOTTOM_LEFT,
                'Bottom Right': ClockPosition.BOTTOM_RIGHT,
                'Bottom Center': ClockPosition.BOTTOM_CENTER,
            }
            position = position_map.get(position_str, ClockPosition.TOP_RIGHT)
            
            # Create clock widget
            logger.debug(f"Creating ClockWidget: format={time_format.value}, position={position_str}, "
                        f"show_seconds={show_seconds}, timezone={timezone_str}, show_tz={show_timezone}, "
                        f"font_size={font_size}")
            
            try:
                self.clock_widget = ClockWidget(self, time_format, position, show_seconds, 
                                               timezone_str, show_timezone)
                logger.debug("ClockWidget created successfully")
                
                # Set font family if specified
                font_family = clock_settings.get('font_family', 'Segoe UI')
                if hasattr(self.clock_widget, 'set_font_family'):
                    self.clock_widget.set_font_family(font_family)
                    logger.debug(f"Font family set to {font_family}")
                
                self.clock_widget.set_font_size(font_size)
                logger.debug(f"Font size set to {font_size}")
                
                self.clock_widget.set_margin(margin)
                logger.debug(f"Margin set to {margin}")
                
                # Convert color array to QColor
                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                self.clock_widget.set_text_color(qcolor)
                logger.debug(f"Color set to RGBA({color[0]}, {color[1]}, {color[2]}, {color[3]})")
                
                # Set background frame if enabled
                show_background = _to_bool(clock_settings.get('show_background', False), False)
                self.clock_widget.set_show_background(show_background)
                logger.debug(f"Background frame: {show_background}")
                
                # Set background opacity
                bg_opacity = clock_settings.get('bg_opacity', 0.9)
                self.clock_widget.set_background_opacity(bg_opacity)
                logger.debug(f"Background opacity: {bg_opacity * 100:.0f}%")
                
                # Ensure clock is on top of image
                self.clock_widget.raise_()
                
                self.clock_widget.start()
                logger.info(f"✅ Clock widget started: {position_str}, {time_format.value}, "
                           f"font={font_size}px, seconds={show_seconds}")
                
                # Verify widget is visible
                logger.debug(f"Clock widget visible: {self.clock_widget.isVisible()}, "
                            f"size: {self.clock_widget.width()}x{self.clock_widget.height()}, "
                            f"pos: ({self.clock_widget.x()}, {self.clock_widget.y()})")
                logger.debug("Clock widget Z-order raised to top")
                
            except Exception as e:
                logger.error(f"Failed to create/configure clock widget: {e}", exc_info=True)
        else:
            logger.debug("Clock widget disabled in settings")
        
        # Weather widget
        weather_settings = widgets.get('weather', {}) if isinstance(widgets, dict) else {}
        weather_enabled = _to_bool(weather_settings.get('enabled', False), False)
        if weather_enabled:
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
        if not hw_accel:
            return
        overlay = getattr(self, "_srpss_gl_xfade_overlay", None)
        if overlay is None or not isinstance(overlay, _GLFadeWidget):
            w, h = self.width(), self.height()
            if w <= 0 or h <= 0 or base_pixmap is None or base_pixmap.isNull():
                return
            overlay = _GLFadeWidget(self, base_pixmap, base_pixmap)
            overlay.setGeometry(0, 0, w, h)
            setattr(self, "_srpss_gl_xfade_overlay", overlay)
            if getattr(self, "_resource_manager", None):
                try:
                    self._resource_manager.register_qt(overlay, description="GL Crossfade persistent overlay (warm-up)")
                except Exception:
                    pass
        # Present once with the current image to ensure context/FBO are ready
        try:
            overlay.set_alpha(1.0)
            overlay.setVisible(True)
            try:
                overlay.raise_()
            except Exception:
                pass
            # Keep clock above overlay
            if self.clock_widget:
                try:
                    self.clock_widget.raise_()
                except Exception:
                    pass
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
    
    def _prewarm_gl_contexts(self) -> None:
        """
        Pre-warm all GL contexts by creating and immediately destroying dummy overlays.
        
        This eliminates first-run GL initialization overhead that can cause flicker.
        Called once during DisplayWidget initialization if HW acceleration is enabled.
        """
        import time
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
        
        # Import all GL overlay widget classes
        try:
            from transitions.gl_crossfade_transition import _GLFadeWidget
            from transitions.gl_slide_transition import _GLSlideWidget
            from transitions.slide_transition import SlideDirection
            from transitions.gl_wipe_transition import _GLWipeWidget
            from transitions.wipe_transition import WipeDirection
            from transitions.gl_diffuse_transition import _GLDiffuseWidget, _Cell
            from transitions.gl_block_puzzle_flip_transition import _GLBlockFlipWidget, _GLFlipBlock
            from PySide6.QtCore import QRect
        except ImportError as e:
            logger.warning(f"[PREWARM] Failed to import GL overlay classes: {e}")
            return
        
        overlays_to_prewarm = [
            ("Crossfade", "_srpss_gl_xfade_overlay", lambda: _GLFadeWidget(self, dummy, dummy)),
            ("Slide", "_srpss_gl_slide_overlay", lambda: _GLSlideWidget(self, dummy, dummy, SlideDirection.LEFT)),
            ("Wipe", "_srpss_gl_wipe_overlay", lambda: _GLWipeWidget(self, dummy, dummy, WipeDirection.LEFT_TO_RIGHT)),
            ("Diffuse", "_srpss_gl_diffuse_overlay", lambda: _GLDiffuseWidget(self, dummy, dummy, [_Cell(QRect(0, 0, w, h))])),
            ("Block", "_srpss_gl_blockflip_overlay", lambda: _GLBlockFlipWidget(self, dummy, dummy, [_GLFlipBlock(QRect(0, 0, w, h))])),
        ]
        
        prewarmed_count = 0
        for name, attr_name, create_fn in overlays_to_prewarm:
            try:
                # Create overlay
                per_overlay_start = time.time()
                overlay = create_fn()
                overlay.setGeometry(0, 0, w, h)
                overlay.show()
                
                # Force GL initialization
                overlay.makeCurrent()
                overlay.repaint()
                
                # Wait briefly for GL init (with timeout)
                timeout_ms = 150
                start = time.time()
                while not overlay.is_ready_for_display():
                    QApplication.processEvents()
                    if (time.time() - start) * 1000 > timeout_ms:
                        logger.debug(f"[PREWARM] {name} timeout, continuing")
                        break
                    time.sleep(0.001)
                
                # STORE as persistent overlay instead of deleting
                overlay.hide()
                setattr(self, attr_name, overlay)
                prewarmed_count += 1
                per_elapsed_ms = (time.time() - per_overlay_start) * 1000
                if per_elapsed_ms > 250:
                    logger.warning(f"[PREWARM] {name} overlay initialization slow: {per_elapsed_ms:.1f}ms")
                else:
                    logger.debug(f"[PREWARM] {name} overlay initialization {per_elapsed_ms:.1f}ms")
                
            except Exception as e:
                logger.warning(f"[PREWARM] Failed to pre-warm {name}: {e}")
                continue
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[PREWARM] GL context pre-warming complete for screen {self.screen_index}: "
                   f"{prewarmed_count}/{len(overlays_to_prewarm)} overlays in {elapsed_ms:.1f}ms")
    
    def _create_transition(self) -> Optional[BaseTransition]:
        """
        Create a transition based on settings.
        
        Returns:
            Transition instance or None if transitions disabled
        """
        if not self.settings_manager:
            return None
        
        # Support both nested dict and dot notation for settings
        transitions_settings = self.settings_manager.get('transitions', {})
        transition_type = transitions_settings.get('type', self.settings_manager.get('transitions.type', 'Crossfade'))
        # Apply random selection if enabled (choice synced via settings key on each rotation)
        try:
            rnd = transitions_settings.get('random_always', self.settings_manager.get('transitions.random_always', False))
            if isinstance(rnd, str):
                rnd = rnd.lower() in ('true', '1', 'yes')
            if rnd:
                chosen = self.settings_manager.get('transitions.random_choice', None)
                if chosen:
                    transition_type = chosen
        except Exception:
            pass
        # BUG FIX #5: Increased default from 1000ms to 1300ms (30% slower) for smoother crossfades
        duration_ms = transitions_settings.get('duration_ms', self.settings_manager.get('transitions.duration_ms', 1300))
        
        try:
            from transitions import (
                CrossfadeTransition, GLCrossfadeTransition,
                SlideTransition, GLSlideTransition, SlideDirection,
                DiffuseTransition,
                BlockPuzzleFlipTransition, GLBlockPuzzleFlipTransition,
                WipeTransition, GLWipeTransition, WipeDirection
            )
            
            # Read common options
            easing_str = transitions_settings.get('easing', self.settings_manager.get('transitions.easing', 'Auto'))
            hw_accel = self.settings_manager.get('display.hw_accel', False)
            # Handle string boolean values from settings file
            if isinstance(hw_accel, str):
                hw_accel = hw_accel.lower() in ('true', '1', 'yes')

            if transition_type == 'Crossfade':
                if hw_accel:
                    return GLCrossfadeTransition(duration_ms, easing_str)
                return CrossfadeTransition(duration_ms, easing_str)
            
            elif transition_type == 'Slide':
                import random
                direction_str = transitions_settings.get('direction', self.settings_manager.get('transitions.direction', 'Random'))
                direction_map = {
                    'Left to Right': SlideDirection.LEFT,
                    'Right to Left': SlideDirection.RIGHT,
                    'Top to Bottom': SlideDirection.DOWN,
                    'Bottom to Top': SlideDirection.UP,
                    'Diagonal TL-BR': SlideDirection.DIAG_TL_BR,
                    'Diagonal TR-BL': SlideDirection.DIAG_TR_BL
                }
                
                # Only randomize if direction is explicitly 'Random' AND random_always is disabled
                # If random_always is enabled, the engine already chose a direction
                rnd_always = transitions_settings.get('random_always', self.settings_manager.get('transitions.random_always', False))
                if isinstance(rnd_always, str):
                    rnd_always = rnd_always.lower() in ('true', '1', 'yes')
                
                if direction_str == 'Random' and not rnd_always:
                    # Avoid repeating the previous direction
                    all_dirs = [
                        SlideDirection.LEFT, SlideDirection.RIGHT,
                        SlideDirection.UP, SlideDirection.DOWN
                    ]
                    last_dir = self.settings_manager.get('transitions.last_slide_direction', None)
                    # Map last string to enum if present
                    str_to_enum = {
                        'Left to Right': SlideDirection.LEFT,
                        'Right to Left': SlideDirection.RIGHT,
                        'Top to Bottom': SlideDirection.DOWN,
                        'Bottom to Top': SlideDirection.UP,
                    }
                    last_enum = str_to_enum.get(last_dir) if isinstance(last_dir, str) else None
                    candidates = [d for d in all_dirs if d != last_enum] if last_enum in all_dirs else all_dirs
                    direction = random.choice(candidates) if candidates else random.choice(all_dirs)
                    # Persist last for next time
                    enum_to_str = {
                        SlideDirection.LEFT: 'Left to Right',
                        SlideDirection.RIGHT: 'Right to Left',
                        SlideDirection.DOWN: 'Top to Bottom',
                        SlideDirection.UP: 'Bottom to Top',
                    }
                    self.settings_manager.set('transitions.last_slide_direction', enum_to_str.get(direction, 'Left to Right'))
                else:
                    direction = direction_map.get(direction_str, SlideDirection.LEFT)
                
                if hw_accel:
                    return GLSlideTransition(duration_ms, direction, easing_str)
                return SlideTransition(duration_ms, direction, easing_str)
            
            elif transition_type == 'Wipe':
                import random
                # Check if we have a persisted wipe direction from random_always
                wipe_dir_str = self.settings_manager.get('transitions.wipe_direction', None)
                
                direction_map = {
                    'Left to Right': WipeDirection.LEFT_TO_RIGHT,
                    'Right to Left': WipeDirection.RIGHT_TO_LEFT,
                    'Top to Bottom': WipeDirection.TOP_TO_BOTTOM,
                    'Bottom to Top': WipeDirection.BOTTOM_TO_TOP,
                    'Diagonal TL-BR': WipeDirection.DIAG_TL_BR,
                    'Diagonal TR-BL': WipeDirection.DIAG_TR_BL
                }
                
                if wipe_dir_str and wipe_dir_str in direction_map:
                    # Use persisted direction from random_always
                    direction = direction_map[wipe_dir_str]
                else:
                    # Pick a random wipe direction (includes diagonals) without repeating last if possible
                    all_wipes = [
                        WipeDirection.LEFT_TO_RIGHT, WipeDirection.RIGHT_TO_LEFT,
                        WipeDirection.TOP_TO_BOTTOM, WipeDirection.BOTTOM_TO_TOP,
                        WipeDirection.DIAG_TL_BR, WipeDirection.DIAG_TR_BL
                    ]
                    last_wipe = self.settings_manager.get('transitions.last_wipe_direction', None)
                    # Map last string to enum if present
                    str_to_enum = {
                        'Left to Right': WipeDirection.LEFT_TO_RIGHT,
                        'Right to Left': WipeDirection.RIGHT_TO_LEFT,
                        'Top to Bottom': WipeDirection.TOP_TO_BOTTOM,
                        'Bottom to Top': WipeDirection.BOTTOM_TO_TOP,
                        'Diagonal TL-BR': WipeDirection.DIAG_TL_BR,
                        'Diagonal TR-BL': WipeDirection.DIAG_TR_BL,
                    }
                    last_enum = str_to_enum.get(last_wipe) if isinstance(last_wipe, str) else None
                    candidates = [d for d in all_wipes if d != last_enum] if last_enum in all_wipes else all_wipes
                    direction = random.choice(candidates) if candidates else random.choice(all_wipes)
                    # Persist last for next time
                    enum_to_str = {
                        WipeDirection.LEFT_TO_RIGHT: 'Left to Right',
                        WipeDirection.RIGHT_TO_LEFT: 'Right to Left',
                        WipeDirection.TOP_TO_BOTTOM: 'Top to Bottom',
                        WipeDirection.BOTTOM_TO_TOP: 'Bottom to Top',
                        WipeDirection.DIAG_TL_BR: 'Diagonal TL-BR',
                        WipeDirection.DIAG_TR_BL: 'Diagonal TR-BL',
                    }
                    self.settings_manager.set('transitions.last_wipe_direction', enum_to_str.get(direction, 'Left to Right'))
                if hw_accel:
                    return GLWipeTransition(duration_ms, direction, easing_str)
                return WipeTransition(duration_ms, direction, easing_str)
            
            elif transition_type == 'Diffuse':
                diffuse_settings = transitions_settings.get('diffuse', {})
                block_size = diffuse_settings.get('block_size', 
                    self.settings_manager.get('transitions.diffuse.block_size', 50))
                shape = diffuse_settings.get('shape', 
                    self.settings_manager.get('transitions.diffuse.shape', 'Rectangle'))
                return DiffuseTransition(duration_ms, block_size, shape)
            
            elif transition_type == 'Block Puzzle Flip':
                block_flip = transitions_settings.get('block_flip', {})
                rows = block_flip.get('rows', self.settings_manager.get('transitions.block_flip.rows', 4))
                cols = block_flip.get('cols', self.settings_manager.get('transitions.block_flip.cols', 6))
                if hw_accel:
                    return GLBlockPuzzleFlipTransition(duration_ms, rows, cols)
                return BlockPuzzleFlipTransition(duration_ms, rows, cols)
            
            else:
                logger.warning(f"Unknown transition type: {transition_type}, using Crossfade")
                return CrossfadeTransition(duration_ms)
        
        except Exception as e:
            logger.error(f"Failed to create transition: {e}", exc_info=True)
            return None
    
    def set_image(self, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Display a new image with transition.
        
        Args:
            pixmap: Image to display
            image_path: Path to image (for logging/events)
        """
        # If a transition is already running, skip this call (single-skip policy)
        if getattr(self, "_current_transition", None) is not None and self._current_transition.is_running():
            logger.info("Transition in progress - skipping this image request per policy")
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
        
        try:
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
            new_pixmap = ImageProcessor.process_image(
                pixmap,
                screen_size,
                self.display_mode,
                use_lanczos,
                sharpen
            )
            
            # Keep original pixmap for pan & scan (will be used after transition)
            original_pixmap = pixmap
            
            self.error_message = None
            
            # Set DPR on the processed pixmap for proper display scaling
            new_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            
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
            
            # Use transition for all images (including first)
            if self.settings_manager:
                transition = self._create_transition()
                if transition:
                    self._current_transition = transition
                    
                    # For first image, create black pixmap as "previous"
                    if not self.current_pixmap:
                        # Create black pixmap matching display size
                        black_pixmap = QPixmap(new_pixmap.size())
                        black_pixmap.fill(Qt.GlobalColor.black)
                        try:
                            black_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
                        except Exception:
                            pass
                        self.previous_pixmap = black_pixmap
                        logger.debug("[INIT] Created black pixmap for first transition (eliminates init flicker)")
                    else:
                        self.previous_pixmap = self.current_pixmap
                    
                    # Connect transition finished signal
                    # Pass both processed pixmap (for display) and original (for pan & scan)
                    # FIX: Use default args to capture by value (not by reference)
                    transition.finished.connect(lambda np=new_pixmap, op=original_pixmap, 
                        ip=image_path, pse=pan_and_scan_enabled: 
                        self._on_transition_finished(np, op, ip, pse))
                    
                    # Start transition
                    success = transition.start(self.previous_pixmap, new_pixmap, self)
                    if success:
                        # Keep widgets above any overlay/labels created by the transition
                        if self.clock_widget:
                            try:
                                self.clock_widget.raise_()
                                if hasattr(self.clock_widget, '_tz_label') and self.clock_widget._tz_label:
                                    self.clock_widget._tz_label.raise_()
                            except Exception:
                                pass
                        if self.weather_widget:
                            try:
                                self.weather_widget.raise_()
                            except Exception:
                                pass
                        logger.debug(f"Transition started: {transition.__class__.__name__}")
                        return  # Transition will update display
                    else:
                        logger.warning("Transition failed to start, displaying immediately")
                        transition.cleanup()
                        self._current_transition = None
            
            # No transition - display immediately
            self.current_pixmap = new_pixmap
            # Ensure DPR is set
            if self.current_pixmap:
                self.current_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            
            # Start pan and scan if enabled
            if pan_and_scan_enabled:
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
                
                # Use original uncropped pixmap for pan & scan
                try:
                    init_off = self._pan_and_scan.preview_offset(original_pixmap, self.size())
                    self._pan_and_scan.set_initial_offset(init_off)
                except Exception:
                    pass
                self._pan_and_scan.set_image(original_pixmap, self._image_label, self.size())
                
                # Ensure label is visible and on top
                self._image_label.show()
                self._image_label.raise_()
                
                # Lower clock widget to be above pan & scan
                if self.clock_widget:
                    self.clock_widget.raise_()
                
                self._pan_and_scan.start()
            else:
                self._pan_and_scan.enable(False)
                if self._image_label:
                    self._image_label.hide()
                self.update()
                # Warm-up GL overlay now that the first image is presented
                try:
                    self._warm_up_gl_overlay(self.current_pixmap)
                except Exception:
                    pass
            
            logger.debug(f"Image displayed: {image_path} ({pixmap.width()}x{pixmap.height()})")
            self.image_displayed.emit(image_path)
        
        except Exception as e:
            logger.error(f"Failed to process image: {e}", exc_info=True)
            self.error_message = f"Error processing image: {e}"
            self.current_pixmap = None
            self.update()
    
    def _on_transition_finished(self, new_pixmap: QPixmap, original_pixmap: QPixmap, 
                                  image_path: str, pan_enabled: bool) -> None:
        """
        Handle transition completion.
        
        Args:
            new_pixmap: The processed pixmap (cropped/filled) for display
            original_pixmap: The original uncropped pixmap for pan & scan
            image_path: Path to the image
            pan_enabled: Whether pan & scan should be enabled
        """
        transition_to_clean = None
        if self._current_transition:
            transition_to_clean = self._current_transition
            self._current_transition = None  # Clear reference first

        self.current_pixmap = new_pixmap
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
            if self.clock_widget:
                self.clock_widget.raise_()
                if hasattr(self.clock_widget, '_tz_label') and self.clock_widget._tz_label:
                    self.clock_widget._tz_label.raise_()
            if self.weather_widget:
                self.weather_widget.raise_()
            
            self._pan_and_scan.start()
        else:
            self._pan_and_scan.enable(False)
            if self._image_label:
                self._image_label.hide()
            # Ensure widgets stay visible after transition
            if self.clock_widget:
                self.clock_widget.raise_()
                if hasattr(self.clock_widget, '_tz_label') and self.clock_widget._tz_label:
                    self.clock_widget._tz_label.raise_()
            if self.weather_widget:
                self.weather_widget.raise_()
            self.update()
        
        # After the display reflects the new pixmap (and optional pan), clean up
        # Ensure base repaint is flushed before we remove any overlay to avoid flicker
        try:
            self.repaint()
        except Exception:
            pass
        if transition_to_clean:
            try:
                transition_to_clean.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up transition: {e}")
        
        logger.debug(f"Transition completed, image displayed: {image_path}")
        self.image_displayed.emit(image_path)
    
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
        # Stop any running transition
        if self._current_transition:
            transition_to_stop = self._current_transition
            self._current_transition = None  # Clear reference first
            try:
                transition_to_stop.stop()
                transition_to_stop.cleanup()
            except Exception as e:
                logger.warning(f"Error stopping transition in clear(): {e}")
        # Ensure overlays are hidden to prevent residual frames during exit
        try:
            hide_all_overlays(self)
        except Exception:
            pass

        self.current_pixmap = None
        self.previous_pixmap = None
        self.error_message = None
        self.update()

    def show_error(self, message: str) -> None:
        """Show error message on the display widget."""
        self.error_message = message
        self.current_pixmap = None
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

        painter = QPainter(self)
        # Fill with black background
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        
        # Draw image if available
        if self.current_pixmap and not self.current_pixmap.isNull():
            try:
                painter.drawPixmap(self.rect(), self.current_pixmap)
            except Exception:
                painter.drawPixmap(0, 0, self.current_pixmap)
        
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
        """Handle mouse press - exit on any click."""
        logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
        self.exit_requested.emit()
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move - exit if moved beyond threshold."""
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
        """
        Get information about this display.
        
        Returns:
            Dict with display information
        """
        return {
            'screen_index': self.screen_index,
            'display_mode': str(self.display_mode),
            'size': f"{self.width()}x{self.height()}",
            'has_image': self.current_pixmap is not None,
            'has_error': self.error_message is not None
        }
