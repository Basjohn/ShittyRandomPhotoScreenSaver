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
from core.logging.logger import get_logger

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
        self._current_transition: Optional[BaseTransition] = None
        self._image_label: Optional[QLabel] = None  # For pan and scan
        self._pan_and_scan = PanAndScan(self)
        self._screen = None  # Store screen reference for DPI
        self._device_pixel_ratio = 1.0  # DPI scaling factor
        self._initial_mouse_pos = None  # Track mouse movement for exit
        self._mouse_move_threshold = 10  # Pixels of movement before exit
        
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
        
        # Setup overlay widgets AFTER geometry is set
        if self.settings_manager:
            self._setup_widgets()
    
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
        if clock_settings.get('enabled', False):
            # Parse settings
            time_format = TimeFormat.TWELVE_HOUR if clock_settings.get('format', '12h') == '12h' else TimeFormat.TWENTY_FOUR_HOUR
            position_str = clock_settings.get('position', 'Top Right')
            show_seconds = clock_settings.get('show_seconds', False)
            timezone_str = clock_settings.get('timezone', 'local')
            show_timezone = clock_settings.get('show_timezone', False)
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
                
                self.clock_widget.set_font_size(font_size)
                logger.debug(f"Font size set to {font_size}")
                
                self.clock_widget.set_margin(margin)
                logger.debug(f"Margin set to {margin}")
                
                # Convert color array to QColor
                from PySide6.QtGui import QColor
                qcolor = QColor(color[0], color[1], color[2], color[3])
                self.clock_widget.set_text_color(qcolor)
                logger.debug(f"Color set to RGBA({color[0]}, {color[1]}, {color[2]}, {color[3]})")
                
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
        # BUG FIX #5: Increased default from 1000ms to 1300ms (30% slower) for smoother crossfades
        duration_ms = transitions_settings.get('duration_ms', self.settings_manager.get('transitions.duration_ms', 1300))
        
        try:
            from transitions import (
                CrossfadeTransition, SlideTransition, DiffuseTransition,
                BlockPuzzleFlipTransition, WipeTransition,
                SlideDirection, WipeDirection
            )
            
            if transition_type == 'Crossfade':
                return CrossfadeTransition(duration_ms)
            
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
                
                if direction_str == 'Random':
                    # Pick a random direction
                    direction = random.choice([SlideDirection.LEFT, SlideDirection.RIGHT, 
                                              SlideDirection.UP, SlideDirection.DOWN])
                else:
                    direction = direction_map.get(direction_str, SlideDirection.LEFT)
                
                return SlideTransition(duration_ms, direction)
            
            elif transition_type == 'Wipe':
                import random
                # Pick a random wipe direction
                direction = random.choice([WipeDirection.LEFT_TO_RIGHT, WipeDirection.RIGHT_TO_LEFT,
                                          WipeDirection.TOP_TO_BOTTOM, WipeDirection.BOTTOM_TO_TOP])
                return WipeTransition(duration_ms, direction)
            
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
            # Get quality settings
            use_lanczos = False
            sharpen = False
            pan_and_scan_enabled = False
            if self.settings_manager:
                use_lanczos = self.settings_manager.get('display.use_lanczos', False)
                if isinstance(use_lanczos, str):
                    use_lanczos = use_lanczos.lower() == 'true'
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
            
            # If we have a previous image, use transition
            if self.current_pixmap and self.settings_manager:
                transition = self._create_transition()
                if transition:
                    self._current_transition = transition
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
                        logger.debug(f"Transition started: {transition.__class__.__name__}")
                        return  # Transition will update display
                    else:
                        logger.warning("Transition failed to start, displaying immediately")
                        transition.cleanup()
                        self._current_transition = None
            
            # No transition or first image - display immediately
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
        if self._current_transition:
            transition_to_clean = self._current_transition
            self._current_transition = None  # Clear reference first
            try:
                transition_to_clean.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up transition: {e}")
        
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
            self._pan_and_scan.set_image(original_pixmap, self._image_label, self.size())
            
            # Ensure label is visible and on top
            self._image_label.show()
            self._image_label.raise_()
            
            # Keep clock above pan & scan
            if self.clock_widget:
                self.clock_widget.raise_()
            
            self._pan_and_scan.start()
        else:
            self._pan_and_scan.enable(False)
            if self._image_label:
                self._image_label.hide()
            self.update()
        
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
        
        self.current_pixmap = None
        self.previous_pixmap = None
        self.error_message = None
        self.update()
        logger.debug("Display cleared")
    
    def show_error(self, message: str) -> None:
        """
        Show error message.
        
        Args:
            message: Error message to display
        """
        self.error_message = message
        self.current_pixmap = None
        self.update()
        logger.warning(f"[FALLBACK] Showing error: {message}")
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint event - draw current image or error message."""
        painter = QPainter(self)
        
        # Fill with black background
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        
        # Draw image if available
        if self.current_pixmap and not self.current_pixmap.isNull():
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
