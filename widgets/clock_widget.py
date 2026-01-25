"""
Clock widget for screensaver overlay.

Displays current time with configurable format, position, and styling.
"""
from typing import Optional, Union, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from enum import Enum
import math
import time
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QColor, QPainter, QPen, QPaintEvent, QPainterPath, QPainterPathStroker, QPixmap
from shiboken6 import Shiboken

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import ShadowFadeProfile, apply_widget_shadow
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from core.logging.logger import get_logger
from core.performance import widget_paint_sample

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.threading import ThreadManager


class TimeFormat(Enum):
    """Time format options."""
    TWELVE_HOUR = "12h"
    TWENTY_FOUR_HOUR = "24h"


class ClockPosition(Enum):
    """Clock position on screen."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class ClockWidget(BaseOverlayWidget):
    """
    Clock widget for displaying time on screensaver.
    
    Extends BaseOverlayWidget for common styling/positioning functionality.
    
    Features:
    - 12h/24h format
    - Configurable position
    - Auto-update every second
    - Customizable font and colors
    - Show/hide seconds
    - Digital and analog display modes
    """
    
    # Signals
    time_updated = Signal(str)  # Emits formatted time string
    
    # Override defaults for clock
    DEFAULT_FONT_SIZE = 48
    DIGITAL_TZ_GAP = 20
    
    def __init__(self, parent: Optional[QWidget] = None,
                 time_format: TimeFormat = TimeFormat.TWELVE_HOUR,
                 position: ClockPosition = ClockPosition.TOP_RIGHT,
                 show_seconds: bool = True,
                 timezone_str: str = 'local',
                 show_timezone: bool = False):
        """
        Initialize clock widget.
        
        Args:
            parent: Parent widget
            time_format: 12h or 24h format
            position: Screen position
            show_seconds: Whether to show seconds
            timezone_str: Timezone string ('local', pytz timezone, or 'UTC±HH:MM')
            show_timezone: Whether to display timezone abbreviation
        """
        # Convert ClockPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="clock")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True
        
        # Clock-specific settings
        self._time_format = time_format
        self._clock_position = position  # Keep original enum for compatibility
        self._show_seconds = show_seconds
        self._show_timezone = show_timezone
        self._thread_manager: Optional["ThreadManager"] = None
        self._timer_handle: Optional[OverlayTimerHandle] = None
        self._timer = None
        
        # Separate label for timezone
        self._tz_label: Optional[QLabel] = None
        
        # Timezone setup
        self._timezone_str = timezone_str
        self._timezone = self._parse_timezone(timezone_str)
        self._timezone_abbrev = self._get_timezone_abbrev()
        
        # Override base class font size default
        self._font_size = 48
        
        # Display mode: digital (default) or analogue clock-face rendering.
        self._display_mode: str = "digital"
        self._show_numerals: bool = True
        # Optional analogue-only drop shadow under the clock face and hands.
        self._analog_face_shadow: bool = True
        self._analog_shadow_intense: bool = False
        # Digital clock intense shadow (uses base class QGraphicsDropShadowEffect)
        self._digital_shadow_intense: bool = False

        # Last timestamp used for analogue rendering.
        self._current_dt: Optional[datetime] = None
        
        # Static element cache for analog clock face (circle, markers, numerals)
        # Only hands need to be redrawn each second
        self._cached_clock_face: Optional["QPixmap"] = None
        self._cached_clock_face_size: Optional[tuple[int, int]] = None
        self._clock_face_cache_invalidated: bool = True
        # Reusable analog frame buffer to avoid reallocating full-resolution pixmaps each paint
        self._analog_frame_buffer: Optional[QPixmap] = None
        self._analog_frame_buffer_size: Optional[tuple[int, int]] = None
        self._analog_frame_buffer_dpr: Optional[float] = None

        # Setup widget
        self._setup_ui()
        
        # Track if we've been initialized via lifecycle
        self._lifecycle_initialized = True

        # External tick driver toggle (e.g., synthetic benchmark shared timer)
        self._external_tick_driver: bool = False

        logger.debug(f"ClockWidget created (format={time_format.value}, "
                    f"position={position.value}, seconds={show_seconds}, "
                    f"timezone={timezone_str}, show_tz={show_timezone})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        # Use base class styling setup
        self._apply_base_styling()
        
        # Set label properties
        self.setObjectName("clock_main")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Set font with bold weight for clock
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
        # Create timezone label if needed
        if self._show_timezone and self.parent():
            self._create_tz_label()
    
    def _create_tz_label(self) -> None:
        """Create the timezone label."""
        self._tz_label = QLabel(self)
        self._tz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tz_font_size = max(int(self._font_size / 4), 8)
        tz_font = QFont(self._font_family, tz_font_size)
        self._tz_label.setFont(tz_font)
        self._tz_label.setStyleSheet(f"""QLabel {{
            color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                       {self._text_color.blue()}, {self._text_color.alpha()});
            background-color: transparent;
            padding: 0px;
            border: none;
        }}""")
        self._tz_label.hide()

    def _get_tz_label_height_estimate(self) -> int:
        """Estimate timezone label height for padding calculations."""
        if self._tz_label is not None:
            try:
                h = self._tz_label.height()
                if h > 0:
                    return h
                hint = self._tz_label.sizeHint()
                if hint.isValid():
                    return hint.height()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
        tz_font_size = max(int(self._font_size / 4), 8)
        try:
            metrics = QFontMetrics(QFont(self._font_family, tz_font_size, QFont.Weight.Bold))
            return max(tz_font_size, metrics.height())
        except Exception as e:
            logger.debug("[CLOCK] Exception suppressed: %s", e)
            return tz_font_size

    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - update clock display."""
        self._update_time()
    
    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize clock resources (lifecycle hook)."""
        self._lifecycle_initialized = True
        logger.debug("[LIFECYCLE] ClockWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate clock - start timer and show widget (lifecycle hook)."""
        if not self._ensure_thread_manager("ClockWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")

        # Update immediately
        self._update_time()

        if self._external_tick_driver:
            logger.debug("[CLOCK] External tick driver active; skipping internal timer start")
            self._timer_handle = None
            self._timer = None
        else:
            # Start recurring updates
            handle = create_overlay_timer(self, 1000, self._update_time, description="ClockWidget tick")
            self._timer_handle = handle
            self._timer = getattr(handle, "_timer", None)
        
        # Start fade-in
        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                overlay_name = getattr(self, "_overlay_name", "clock")
                parent.request_overlay_fade_sync(overlay_name, lambda: self._start_widget_fade_in(1500))
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
                self._start_widget_fade_in(1500)
        else:
            self._start_widget_fade_in(1500)
        
        logger.debug("[LIFECYCLE] ClockWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate clock - stop timer and hide widget (lifecycle hook)."""
        if self._timer_handle is not None:
            try:
                self._timer_handle.stop()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
            self._timer_handle = None
        
        if self._timer is not None:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        logger.debug("[LIFECYCLE] ClockWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up clock resources (lifecycle hook)."""
        # Stop timer if still running
        self._deactivate_impl()
        
        # Clean up timezone label
        if self._tz_label is not None:
            try:
                self._tz_label.deleteLater()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
            self._tz_label = None
        
        self._lifecycle_initialized = False
        logger.debug("[LIFECYCLE] ClockWidget cleaned up")
    
    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------
    
    def start(self) -> None:
        """Start clock updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Clock already running")
            return
        if not self._ensure_thread_manager("ClockWidget.start"):
            return
        
        # Update immediately
        self._update_time()

        if self._external_tick_driver:
            logger.debug("[CLOCK] External tick driver active; skipping legacy start timer")
            self._timer_handle = None
            self._timer = None
        else:
            # Start recurring updates via the centralized overlay timer helper.
            # Keep the legacy QTimer attribute for compatibility with any
            # existing diagnostics/tests while routing creation through
            # create_overlay_timer so timers participate in ThreadManager /
            # ResourceManager tracking when available.
            handle = create_overlay_timer(self, 1000, self._update_time, description="ClockWidget tick")
            self._timer_handle = handle
            self._timer = getattr(handle, "_timer", None)

        self._enabled = True
        parent = self.parent()

        def _starter() -> None:
            # Guard against widget being deleted before deferred callback runs
            if not Shiboken.isValid(self):
                return
            self._start_widget_fade_in(1500)

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                overlay_name = getattr(self, "_overlay_name", "clock")
                parent.request_overlay_fade_sync(overlay_name, _starter)
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
                _starter()
        else:
            _starter()

        logger.info("Clock widget started")
    
    def stop(self) -> None:
        """Stop clock updates."""
        if not self._enabled:
            return
        
        if self._timer_handle is not None:
            try:
                self._timer_handle.stop()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
            self._timer_handle = None

        if self._timer is not None:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        self._enabled = False
        self.hide()
        
        logger.debug("Clock widget stopped")
    
    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        # Guard against widget being deleted before this method runs
        if not Shiboken.isValid(self):
            return
            
        if duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
            if self._tz_label:
                try:
                    self._tz_label.show()
                    self._tz_label.raise_()
                except Exception as e:
                    logger.debug("[CLOCK] Exception suppressed: %s", e)
            # Only apply widget-level shadow in digital mode. Analog mode uses
            # QPainter-drawn shadows to avoid QGraphicsDropShadowEffect cache corruption.
            if self._display_mode != "analog":
                try:
                    ShadowFadeProfile.attach_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception as e:
                    logger.debug("[CLOCK] Exception suppressed: %s", e)
            self._has_faded_in = True
            return

        if Shiboken.isValid(self) and self.parent():
            try:
                self._update_position()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)

        try:
            self.show()
        except Exception as e:
            logger.debug("[CLOCK] Exception suppressed: %s", e)
        if self._tz_label:
            try:
                self._tz_label.show()
                self._tz_label.raise_()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)

        # Only apply widget-level shadow in digital mode. Analog mode uses
        # QPainter-drawn shadows to avoid QGraphicsDropShadowEffect cache corruption.
        if self._display_mode != "analog":
            try:
                ShadowFadeProfile.start_fade_in(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config or {},
                        has_background_frame=self._show_background,
                    )
                except Exception as e:
                    logger.debug("[CLOCK] Exception suppressed: %s", e)
        self._has_faded_in = True
    
    def is_running(self) -> bool:
        """Check if clock is running."""
        return self._enabled
    
    def _parse_timezone(self, tz_str: str) -> Union[timezone, 'pytz.tzinfo.BaseTzInfo', None]:
        """
        Parse timezone string into timezone object.
        
        Supports:
        - 'local': System local time (None)
        - pytz timezone names: 'US/Eastern', 'Europe/London', etc.
        - Custom UTC offsets: 'UTC+5:30', 'UTC-7', 'UTC+0'
        
        Args:
            tz_str: Timezone string
            
        Returns:
            Timezone object or None for local time
        """
        if tz_str == 'local' or not tz_str:
            return None
        
        # Try pytz timezone
        if PYTZ_AVAILABLE:
            try:
                return pytz.timezone(tz_str)
            except pytz.UnknownTimeZoneError:
                pass
        
        # Try custom UTC offset format: UTC+5:30 or UTC-7
        if tz_str.upper().startswith('UTC'):
            try:
                offset_str = tz_str[3:]  # Remove 'UTC' prefix
                if not offset_str or offset_str == '+0' or offset_str == '-0':
                    return timezone.utc
                
                # Parse sign
                if offset_str[0] in ('+', '-'):
                    sign = 1 if offset_str[0] == '+' else -1
                    offset_str = offset_str[1:]
                else:
                    sign = 1
                
                # Parse hours and minutes
                if ':' in offset_str:
                    hours, minutes = offset_str.split(':')
                    hours = int(hours)
                    minutes = int(minutes)
                else:
                    hours = int(offset_str)
                    minutes = 0
                
                # Create timezone
                offset = timedelta(hours=sign * hours, minutes=sign * minutes)
                return timezone(offset)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse UTC offset '{tz_str}': {e}")
        
        logger.warning(f"Unknown timezone '{tz_str}', using local time")
        return None
    
    def _get_timezone_abbrev(self) -> str:
        """
        Get standardized timezone abbreviation for display.
        
        Returns:
            Timezone abbreviation (e.g., 'SAST', 'UTC', 'GMT', 'EST')
        """
        if self._timezone is None:
            # Local time - get abbreviation
            local_abbrev = time.tzname[time.daylight]
            # Standardize common abbreviations
            return self._standardize_tz_abbrev(local_abbrev)
        
        if PYTZ_AVAILABLE and hasattr(self._timezone, 'zone'):
            # pytz timezone
            now = datetime.now(self._timezone)
            abbrev = now.strftime('%Z')
            return self._standardize_tz_abbrev(abbrev)
        
        # Custom UTC offset
        if isinstance(self._timezone, timezone):
            offset = self._timezone.utcoffset(None)
            if offset == timedelta(0):
                return 'UTC'
            total_seconds = int(offset.total_seconds())
            hours = total_seconds // 3600
            minutes = abs(total_seconds % 3600) // 60
            if minutes == 0:
                return f'UTC{hours:+d}'
            else:
                return f'UTC{hours:+d}:{minutes:02d}'
        
        return ''
    
    def _standardize_tz_abbrev(self, abbrev: str) -> str:
        """
        Standardize timezone abbreviation to common formats.
        
        Args:
            abbrev: Raw timezone abbreviation
            
        Returns:
            Standardized abbreviation
        """
        # Map common variations to standard abbreviations
        abbrev_map = {
            'CAT': 'SAST',  # Central Africa Time -> South Africa Standard Time
            'South Africa Standard Time': 'SAST',
            'GMT Standard Time': 'GMT',
            'GMT Daylight Time': 'BST',
            'Pacific Standard Time': 'PST',
            'Pacific Daylight Time': 'PDT',
            'Eastern Standard Time': 'EST',
            'Eastern Daylight Time': 'EDT',
            'Central Standard Time': 'CST',
            'Central Daylight Time': 'CDT',
            'Mountain Standard Time': 'MST',
            'Mountain Daylight Time': 'MDT',
            'Japan Standard Time': 'JST',
            'China Standard Time': 'CST',
            'India Standard Time': 'IST',
            'Australian Eastern Standard Time': 'AEST',
            'Australian Eastern Daylight Time': 'AEDT',
        }
        
        # Return mapped abbreviation or original if not found
        return abbrev_map.get(abbrev, abbrev)
    
    def _update_time(self) -> None:
        """Update displayed time."""
        try:
            if not Shiboken.isValid(self):
                if getattr(self, "_timer_handle", None) is not None:
                    try:
                        self._timer_handle.stop()  # type: ignore[union-attr]
                    except Exception as e:
                        logger.debug("[CLOCK] Exception suppressed: %s", e)
                    self._timer_handle = None  # type: ignore[assignment]

                if getattr(self, "_timer", None) is not None:
                    try:
                        self._timer.stop()  # type: ignore[union-attr]
                        self._timer.deleteLater()  # type: ignore[union-attr]
                    except Exception as e:
                        logger.debug("[CLOCK] Exception suppressed: %s", e)
                    self._timer = None  # type: ignore[assignment]

                self._enabled = False
                return
        except Exception as e:
            logger.debug("[CLOCK] Exception suppressed: %s", e)
            return

        # Get current time in specified timezone
        if self._timezone is None:
            now = datetime.now()
        else:
            now = datetime.now(self._timezone)

        self._current_dt = now

        # For analogue mode, force the cached clock face (ring + markers +
        # numeral shadows) to be regenerated on the next paint so any
        # cached artefacts are cleared at least once per tick. This adds a
        # small (~1–2ms) cost on the first paint after each tick but avoids
        # long-lived cache corruption.
        if self._display_mode == "analog":
            self._invalidate_clock_face_cache()

        # Format time based on settings
        if self._time_format == TimeFormat.TWELVE_HOUR:
            if self._show_seconds:
                time_str = now.strftime("%I:%M:%S %p")
            else:
                time_str = now.strftime("%I:%M %p")
        else:  # 24-hour
            if self._show_seconds:
                time_str = now.strftime("%H:%M:%S")
            else:
                time_str = now.strftime("%H:%M")

        # Remove leading zero for 12-hour format
        if self._time_format == TimeFormat.TWELVE_HOUR:
            time_str = time_str.lstrip('0')

        timezone_abbrev = self._get_timezone_abbrev() if self._show_timezone else ""
        self._timezone_abbrev = timezone_abbrev

        # Main clock text should not include the timezone; the abbreviation is shown
        # exclusively in the smaller secondary label when enabled.
        if self._display_mode == "analog":
            # Analogue mode uses custom paint; keep the label text empty so
            # the base QLabel paint path only renders the background frame.
            display_text = ""
        else:
            display_text = time_str

        # Plain text display
        self.setText(display_text)
        self.setTextFormat(Qt.TextFormat.PlainText)

        # Update timezone label if shown (digital mode only). When in
        # analogue mode the timezone abbreviation is rendered directly in
        # paintEvent beneath the clock face.
        if self._show_timezone and self._tz_label:
            if self._display_mode != "analog" and timezone_abbrev:
                self._tz_label.setText(timezone_abbrev)
                try:
                    self._tz_label.adjustSize()
                except Exception as e:
                    logger.debug("[CLOCK] Exception suppressed: %s", e)
                self._tz_label.show()
                self._tz_label.raise_()
            else:
                self._tz_label.hide()
        if self._show_background:
            self._update_stylesheet()
            self.adjustSize()

        
        # Adjust size to content in digital mode; analogue mode relies more on
        # its minimum size and custom paint logic.
        if self._display_mode != "analog":
            self.adjustSize()
        
        # Update position (includes timezone label positioning)
        if self.parent():
            self._update_position()
        
        # Emit signal
        self.time_updated.emit(time_str)

        # Note: No need to call update() here - clock face is cached and Qt will
        # automatically trigger repaint when setText() changes the label text.
        # Analog mode hands are drawn in paintEvent which is called automatically.
    
    def _update_position(self) -> None:
        """Update widget position using centralized base class logic.
        
        Delegates to BaseOverlayWidget._update_position() which handles:
        - Margin-based positioning for all 9 anchor positions
        - Visual padding offsets (when background is disabled)
        - Pixel shift and stack offset application
        - Bounds clamping to prevent off-screen drift
        
        For analog mode without background, we set visual padding based on
        the computed analog visual offset so the clock face aligns with
        other widgets at the same margin.
        """
        # Sync ClockPosition to OverlayPosition for base class
        position_map = {
            ClockPosition.TOP_LEFT: OverlayPosition.TOP_LEFT,
            ClockPosition.TOP_CENTER: OverlayPosition.TOP_CENTER,
            ClockPosition.TOP_RIGHT: OverlayPosition.TOP_RIGHT,
            ClockPosition.MIDDLE_LEFT: OverlayPosition.MIDDLE_LEFT,
            ClockPosition.CENTER: OverlayPosition.CENTER,
            ClockPosition.MIDDLE_RIGHT: OverlayPosition.MIDDLE_RIGHT,
            ClockPosition.BOTTOM_LEFT: OverlayPosition.BOTTOM_LEFT,
            ClockPosition.BOTTOM_CENTER: OverlayPosition.BOTTOM_CENTER,
            ClockPosition.BOTTOM_RIGHT: OverlayPosition.BOTTOM_RIGHT,
        }
        
        # Update base class position
        self._position = position_map.get(self._clock_position, OverlayPosition.TOP_RIGHT)
        
        # For analog mode without background, set visual padding based on
        # the computed analog visual offset so the clock face aligns properly
        # NOTE: Set padding directly to avoid recursion (set_visual_padding calls _update_position)
        visual_offset_x, visual_offset_y = self._compute_analog_visual_offset()
        self._visual_padding_top = visual_offset_y
        self._visual_padding_right = visual_offset_x
        self._visual_padding_bottom = visual_offset_y
        self._visual_padding_left = visual_offset_x
        
        # Delegate to base class for centralized margin/positioning logic
        super()._update_position()
        
        # Position timezone label inside the background frame (bottom-right)
        if self._show_timezone and self._tz_label:
            if self._display_mode == "analog":
                tz_x = self.width() - self._tz_label.width() - 18
                tz_y = self.height() - self._tz_label.height() + 4
            else:
                tz_x = max(0, int((self.width() - self._tz_label.width()) / 2))
                tz_y = (
                    self.height()
                    - self.contentsMargins().bottom()
                    + self.DIGITAL_TZ_GAP
                )
            self._tz_label.move(tz_x, tz_y)
    
    def set_time_format(self, time_format: TimeFormat) -> None:
        """
        Set time format.
        
        Args:
            time_format: 12h or 24h format
        """
        self._time_format = time_format
        
        # Update stylesheet to tighten padding when timezone hidden
        self._update_stylesheet()

        # Update display immediately if running
        if self._enabled:
            self._update_time()

    def set_display_mode(self, mode: str) -> None:
        """Set display mode ("digital" or "analog")."""
        mode_l = str(mode).lower()
        if mode_l not in ("digital", "analog"):
            mode_l = "digital"
        if self._display_mode == mode_l:
            return
        self._display_mode = mode_l

        # Digital mode uses automatic text sizing; analogue mode prefers a
        # square footprint based on font size.
        if self._display_mode == "analog":
            # Allocate a larger footprint for the analogue clock so the
            # face, numerals, and below-clock timezone have room without
            # clipping.
            base_side = max(160, int(self._font_size * 4.5))
            self.setMinimumWidth(base_side)
            self.setMinimumHeight(int(base_side * 1.3))
        else:
            self.setMinimumSize(0, 0)

        if self._enabled:
            self._update_time()
        else:
            self.update()

    def set_external_tick_driver(self, enabled: bool) -> None:
        """
        Toggle whether this clock relies on an external/shared tick driver.

        When enabled, the widget skips creating its own overlay timer so an
        external controller (e.g., synthetic benchmark shared tick hub) can
        call `_update_time()` directly.
        """
        flag = bool(enabled)
        if self._external_tick_driver == flag:
            return
        self._external_tick_driver = flag
        if flag:
            if self._timer_handle is not None:
                try:
                    self._timer_handle.stop()
                except Exception as e:
                    logger.debug("[CLOCK] Exception suppressed: %s", e)
                self._timer_handle = None
            if self._timer is not None:
                try:
                    self._timer.stop()
                    self._timer.deleteLater()
                except Exception:
                    pass
                self._timer = None
    
    def set_position(self, position: ClockPosition) -> None:
        """
        Set clock position.
        
        Args:
            position: Screen position
        """
        self._clock_position = position
        # Also update base class position for consistency
        self._position = OverlayPosition(position.value)
        
        # Update position immediately if running
        if self._enabled:
            self._update_position()
    
    def set_show_seconds(self, show_seconds: bool) -> None:
        """
        Set whether to show seconds.
        
        Args:
            show_seconds: True to show seconds
        """
        self._show_seconds = show_seconds
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()

    def set_show_numerals(self, show_numerals: bool) -> None:
        """Enable or disable hour numerals when in analogue mode."""

        self._show_numerals = bool(show_numerals)
        if self._display_mode == "analog":
            self._invalidate_clock_face_cache()
            self.update()

    def set_analog_face_shadow(self, enabled: bool) -> None:
        """Enable or disable the analogue face/hand drop shadow effect."""

        self._analog_face_shadow = bool(enabled)
        if self._display_mode == "analog":
            self._invalidate_clock_face_cache()
            self.update()

    def set_analog_shadow_intense(self, intense: bool) -> None:
        """Enable or disable the intensified analogue shadow styling."""

        self._analog_shadow_intense = bool(intense)
        if self._display_mode == "analog":
            self._invalidate_clock_face_cache()
            self.update()

    def set_digital_shadow_intense(self, intense: bool) -> None:
        """Enable or disable the intensified digital clock shadow styling.
        
        When enabled, the QGraphicsDropShadowEffect has doubled blur radius,
        increased opacity, and larger offset for dramatic visual effect.
        """
        self._digital_shadow_intense = bool(intense)
        # Use base class intense shadow for digital mode
        if self._display_mode == "digital":
            self.set_intense_shadow(intense)

    def set_font_family(self, family: str) -> None:
        """Set font family - override to use bold weight and update tz label."""
        super().set_font_family(family)
        # Use bold weight for clock
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        # Invalidate analog clock face cache since numerals use this font
        self._invalidate_clock_face_cache()
        # Update timezone label font
        self._update_tz_label_font()
        if self._enabled:
            self._update_time()
    
    def set_font_size(self, size: int) -> None:
        """Set font size - override to use bold weight and update tz label."""
        try:
            size_i = int(size)
        except Exception as exc:
            logger.debug("[CLOCK] Exception suppressed: %s", exc)
            size_i = self.DEFAULT_FONT_SIZE
        if size_i <= 0:
            size_i = self.DEFAULT_FONT_SIZE
        super().set_font_size(size_i)
        # Use bold weight for clock
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        # Invalidate analog clock face cache since numerals use this font size
        self._invalidate_clock_face_cache()
        # Update timezone label font
        self._update_tz_label_font()
        if self._enabled:
            self._update_time()

    def set_margin(self, margin: int) -> None:
        try:
            margin_i = int(margin)
        except Exception as e:
            logger.debug("[CLOCK] Exception suppressed: %s", e)
            margin_i = self.DEFAULT_MARGIN
        if margin_i < 0:
            margin_i = self.DEFAULT_MARGIN
        super().set_margin(margin_i)
    
    def _update_tz_label_font(self) -> None:
        """Update timezone label font to match main font with bold weight."""
        if self._tz_label:
            tz_font_size = max(int(self._font_size / 4), 8)
            tz_font = QFont(self._font_family, tz_font_size, QFont.Weight.Bold)
            self._tz_label.setFont(tz_font)
    
    def set_timezone(self, timezone_str: str) -> None:
        """
        Set timezone for clock display.
        
        Args:
            timezone_str: Timezone string ('local', pytz timezone, or 'UTC±HH:MM')
        """
        self._timezone_str = timezone_str
        self._timezone = self._parse_timezone(timezone_str)
        self._timezone_abbrev = self._get_timezone_abbrev()
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()

    def set_show_timezone(self, show_timezone: bool) -> None:
        """
        Set whether to display timezone abbreviation.
        
        Args:
            show_timezone: True to show timezone
        """
        if self._show_timezone == show_timezone:
            # No change
            return

        self._show_timezone = show_timezone
        self._update_stylesheet()

        if show_timezone and self._tz_label is None and self.parent():
            # Lazily create timezone label if needed
            self._tz_label = QLabel(self)
            self._tz_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            tz_font_size = max(int(self._font_size / 4), 8)
            tz_font = QFont(self._font_family, tz_font_size)
            self._tz_label.setFont(tz_font)
            self._tz_label.setStyleSheet(f"""QLabel {{
                color: rgba({self._text_color.red()}, {self._text_color.green()},
                           {self._text_color.blue()}, {self._text_color.alpha()});
                background-color: transparent;
                padding: 0px;
                border: none;
            }}""")
            self._tz_label.hide()
        elif not show_timezone and self._tz_label:
            self._tz_label.hide()

        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        tz_extra_space = 0
        if self._show_timezone and self._display_mode != "analog":
            tz_extra_space = self.DIGITAL_TZ_GAP + self._get_tz_label_height_estimate()

        if self._show_background:
            if self._display_mode == "analog":
                padding_left, padding_top, padding_bottom, _ = self._compute_analog_padding()
                padding_right = padding_left
            else:
                padding_top = 6
                padding_right = 28
                padding_bottom = 6 + tz_extra_space
                padding_left = 21
                padding_right = 28

            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()}, 
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()}, 
                                                                 {self._bg_border_color.green()}, 
                                                                 {self._bg_border_color.blue()}, 
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                    padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;
                }}
            """)
            self.setContentsMargins(padding_left, padding_top, padding_right, padding_bottom)
        else:
            # Transparent background (default)
            if self._display_mode == "analog":
                # Analogue mode without background: use symmetric padding
                # so the clock face is centered within the widget bounds
                padding_left, padding_top, padding_bottom, _ = self._compute_analog_padding()
                padding_right = padding_left
                self.setStyleSheet(f"""
                    QLabel {{
                        color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                                   {self._text_color.blue()}, {self._text_color.alpha()});
                        background-color: transparent;
                        padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;
                    }}
                """)
                self.setContentsMargins(padding_left, padding_top, padding_right, padding_bottom)
            else:
                # Digital mode without background: use asymmetric padding for text alignment
                padding_top = 6
                padding_right = 28
                padding_left = 21
                padding_bottom = 6 + tz_extra_space
                self.setStyleSheet(f"""
                    QLabel {{
                        color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                                   {self._text_color.blue()}, {self._text_color.alpha()});
                        background-color: transparent;
                        padding: {padding_top}px {padding_right}px {padding_bottom}px {padding_left}px;
                    }}
                """)
                self.setContentsMargins(0, 0, 0, tz_extra_space)
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom paint for analogue mode; fall back to QLabel for digital."""

        if self._display_mode != "analog":
            with widget_paint_sample(self, "clock.paint.digital"):
                super().paintEvent(event)
            return

        with widget_paint_sample(self, "clock.paint.analog"):
            self._paint_analog(event)

    def _invalidate_clock_face_cache(self) -> None:
        """Invalidate the cached clock face so it will be regenerated on next paint."""
        self._clock_face_cache_invalidated = True
        self._cached_clock_face = None
        self._invalidate_analog_frame_buffer()

    def _invalidate_analog_frame_buffer(self) -> None:
        """Drop the reusable analog frame buffer so a new pixmap will be allocated."""
        self._analog_frame_buffer = None
        self._analog_frame_buffer_size = None
        self._analog_frame_buffer_dpr = None

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._invalidate_analog_frame_buffer()

    def _regenerate_clock_face_cache(self, width: int, height: int) -> None:
        """Regenerate the cached clock face pixmap with static elements.
        
        This caches the circle, hour markers, and numerals. Only the hands
        need to be redrawn each second, saving ~1.5ms per paint.
        """
        dpr = self.devicePixelRatioF()
        pixmap = QPixmap(int(width * dpr), int(height * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            high_quality_hint = getattr(QPainter.RenderHint, "HighQualityAntialiasing", None)
            if high_quality_hint is not None:
                painter.setRenderHint(high_quality_hint, True)
            else:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            shadow_scale = 1.8 if self._analog_shadow_intense else 1.43
            opacity_scale = 3.0 if self._analog_shadow_intense else 1.82

            def _scaled_alpha(base_alpha: int) -> int:
                return min(255, int(round(base_alpha * opacity_scale)))

            left_pad, top_pad, bottom_margin, tz_font_size = self._compute_analog_padding()
            if self._show_background:
                rect = self.contentsRect()
            else:
                rect = self.rect().adjusted(left_pad, top_pad, -left_pad, -bottom_margin)
            side = min(rect.width(), rect.height())
            if side <= 0:
                return

            center_x = rect.x() + rect.width() // 2
            center_y = rect.y() + rect.height() // 2

            numeral_pt = max(8, min(int(self._font_size * 0.25), max(9, side // 18)))
            numeral_font = QFont(self._font_family, numeral_pt, QFont.Weight.Bold)
            painter.setFont(numeral_font)
            numeral_metrics = painter.fontMetrics()
            numeral_height = numeral_metrics.height()

            numeral_clearance = numeral_height + max(6, numeral_height // 3)
            radius = side // 2 - numeral_clearance
            if radius <= 0:
                return

            drop_offset = 3 if self._analog_shadow_intense else 2
            marker_len = max(6, radius // 10)
            marker_lines: list[tuple[int, int, int, int]] = []
            marker_path = QPainterPath()
            for i in range(12):
                angle = math.radians((i / 12.0) * 360.0 - 90.0)
                cos_a = math.cos(angle)
                sin_a = math.sin(angle)
                outer_x = center_x + int(cos_a * (radius - 2))
                outer_y = center_y + int(sin_a * (radius - 2))
                inner_x = center_x + int(cos_a * (radius - marker_len - 2))
                inner_y = center_y + int(sin_a * (radius - marker_len - 2))
                marker_lines.append((inner_x, inner_y, outer_x, outer_y))
                marker_path.moveTo(inner_x, inner_y)
                marker_path.lineTo(outer_x, outer_y)

            if self._analog_face_shadow:
                base_alpha = max(121, int(self._text_color.alpha() * (0.605 if self._analog_shadow_intense else 0.44)))
                shadow_color = QColor(0, 0, 0, _scaled_alpha(base_alpha))

                ring_path = QPainterPath()
                ring_path.addEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
                ring_stroke = QPainterPathStroker()
                ring_stroke.setWidth(max(4.4, radius * (0.0462 if self._analog_shadow_intense else 0.0286)))
                ring_stroke.setCapStyle(Qt.PenCapStyle.RoundCap)
                ring_stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                ring_shape = ring_stroke.createStroke(ring_path)

                marker_stroke = QPainterPathStroker()
                marker_stroke.setWidth(max(2.2, radius * (0.01584 if self._analog_shadow_intense else 0.01144)))
                marker_stroke.setCapStyle(Qt.PenCapStyle.RoundCap)
                marker_stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                marker_shape = marker_stroke.createStroke(marker_path)

                combined_shadow = QPainterPath()
                combined_shadow.addPath(ring_shape)
                combined_shadow.addPath(marker_shape)
                combined_shadow.translate(drop_offset, drop_offset)

                painter.save()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(shadow_color)
                painter.drawPath(combined_shadow)
                painter.restore()

            face_pen = QPen(self._text_color)
            face_pen.setWidth(max(2, int(round(radius * (0.025 if not self._analog_shadow_intense else 0.032)))))
            painter.setPen(face_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            marker_pen = QPen(self._text_color)
            marker_pen.setWidth(max(2, radius // 60))
            painter.setPen(marker_pen)
            for line in marker_lines:
                painter.drawLine(*line)

            if self._show_numerals:
                roman_map = {
                    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
                    7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII",
                }
                numeral_pull_in = max(2, numeral_height // 3) - 5
                numeral_radius = radius + numeral_height - numeral_pull_in
                painter.setFont(numeral_font)
                for hour in range(1, 13):
                    angle = math.radians((hour / 12.0) * 360.0 - 90.0)
                    cos_a = math.cos(angle)
                    sin_a = math.sin(angle)
                    tx = center_x + int(cos_a * numeral_radius)
                    ty = center_y + int(sin_a * numeral_radius)
                    text = roman_map.get(hour, str(hour))
                    tw = numeral_metrics.horizontalAdvance(text)
                    th = numeral_metrics.height()

                    if self._analog_face_shadow:
                        base_numeral_alpha = max(97, int(self._text_color.alpha() * 0.605))
                        numeral_shadow = QColor(0, 0, 0, _scaled_alpha(base_numeral_alpha))
                        painter.setPen(QPen(numeral_shadow))
                        numeral_offset = max(1, int(round(shadow_scale * 1.56)))
                        painter.drawText(tx - tw // 2 + numeral_offset, ty + th // 4 + numeral_offset, text)

                    painter.setPen(QPen(self._text_color))
                    painter.drawText(tx - tw // 2, ty + th // 4, text)
        finally:
            painter.end()

        self._cached_clock_face = pixmap
        self._cached_clock_face_size = (width, height)
        self._clock_face_cache_invalidated = False

    def _paint_analog(self, event: QPaintEvent) -> None:
        """Paint analog clock face, hands, and numerals.
        
        Uses cached pixmap for static elements (face, markers, numerals) and
        draws hands fresh each frame into a composited buffer to prevent
        hand trails on transparent backgrounds.
        """
        if self._current_dt is None:
            if self._timezone is None:
                now = datetime.now()
            else:
                now = datetime.now(self._timezone)
        else:
            now = self._current_dt

        # Check if cache needs regeneration
        current_size = (self.width(), self.height())
        if (self._clock_face_cache_invalidated or 
            self._cached_clock_face is None or
            self._cached_clock_face_size != current_size):
            self._regenerate_clock_face_cache(current_size[0], current_size[1])

        # Create a fresh frame buffer each paint to prevent hand accumulation
        # on transparent backgrounds. We composite: cached face + fresh hands.
        dpr = self.devicePixelRatioF()
        frame_buffer = self._acquire_analog_frame_buffer(self.width(), self.height(), dpr)
        frame_buffer.fill(Qt.GlobalColor.transparent)
        
        # Draw into frame buffer
        fb_painter = QPainter(frame_buffer)
        try:
            fb_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            high_quality_hint = getattr(QPainter.RenderHint, "HighQualityAntialiasing", None)
            if high_quality_hint is not None:
                fb_painter.setRenderHint(high_quality_hint, True)
            else:
                fb_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            # Draw cached clock face (static elements)
            if self._cached_clock_face is not None:
                fb_painter.drawPixmap(0, 0, self._cached_clock_face)

            # Now draw only the dynamic elements (hands)
            shadow_scale = 1.5 if self._analog_shadow_intense else 1.1
            opacity_scale = 2.0 if self._analog_shadow_intense else 1.4

            def _scaled_alpha(base_alpha: int) -> int:
                return min(255, int(round(base_alpha * opacity_scale)))

            left_pad, top_pad, bottom_margin, tz_font_size = self._compute_analog_padding()
            if self._show_background:
                rect = self.contentsRect()
            else:
                rect = self.rect().adjusted(left_pad, top_pad, -left_pad, -bottom_margin)
            side = min(rect.width(), rect.height())
            if side <= 0:
                fb_painter.end()
                return

            center_x = rect.x() + rect.width() // 2
            center_y = rect.y() + rect.height() // 2

            numeral_pt = max(8, min(int(self._font_size * 0.25), max(9, side // 18)))
            numeral_font = QFont(self._font_family, numeral_pt, QFont.Weight.Bold)
            fb_painter.setFont(numeral_font)
            numeral_metrics = fb_painter.fontMetrics()
            numeral_height = numeral_metrics.height()

            numeral_clearance = numeral_height + max(6, numeral_height // 3)
            radius = side // 2 - numeral_clearance
            if radius <= 0:
                fb_painter.end()
                return

            # Helper to draw a hand with an optional bottom-right shadow.
            def _draw_hand(angle_deg: float, length: float, thickness: int, draw_shadow: bool = True) -> None:
                angle = math.radians(angle_deg - 90.0)
                cos_a = math.cos(angle)
                sin_a = math.sin(angle)
                ex = center_x + int(cos_a * length)
                ey = center_y + int(sin_a * length)

                if self._analog_face_shadow:
                    base_hand_alpha = max(69, int(self._text_color.alpha() * 0.504))
                    shadow_color = QColor(0, 0, 0, _scaled_alpha(base_hand_alpha))
                    shadow_pen = QPen(shadow_color)
                    shadow_pen.setWidthF(max(1.5, float(thickness)) * shadow_scale)
                    shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    shadow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    fb_painter.setPen(shadow_pen)
                    hand_offset = max(2, int(round(2.6 * shadow_scale)))
                    fb_painter.drawLine(center_x + hand_offset, center_y + hand_offset, ex + hand_offset, ey + hand_offset)

                hand_pen = QPen(self._text_color)
                hand_pen.setWidthF(max(1.5, float(thickness)))
                hand_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                hand_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                fb_painter.setPen(hand_pen)
                fb_painter.drawLine(center_x, center_y, ex, ey)

            # Compute hand angles
            sec = now.second + now.microsecond / 1_000_000.0
            minute = now.minute + sec / 60.0
            hour = (now.hour % 12) + minute / 60.0

            hour_angle = (hour / 12.0) * 360.0
            minute_angle = (minute / 60.0) * 360.0
            second_angle = (sec / 60.0) * 360.0

            # Draw hands in order: second, hour, minute so the seconds hand sits below.
            # The seconds hand is drawn without a drop shadow to avoid shadow
            # accumulation artifacts while keeping hour/minute shadows intact.
            if self._show_seconds:
                _draw_hand(second_angle, radius * 0.85, 1, draw_shadow=False)
            _draw_hand(hour_angle, radius * 0.52, max(3, radius // 15), draw_shadow=True)
            _draw_hand(minute_angle, radius * 0.72, max(2, radius // 20), draw_shadow=True)

            # Timezone abbreviation rendered below the analogue clock, centred horizontally.
            if self._show_timezone and self._timezone_abbrev:
                tz_font = QFont(self._font_family, tz_font_size, QFont.Weight.Bold)
                fb_painter.setFont(tz_font)
                tz_metrics = fb_painter.fontMetrics()
                tz_height = tz_metrics.height()
                text = self._timezone_abbrev

                tz_y = center_y + radius + numeral_height + tz_height + 4
                tz_x = center_x - tz_metrics.horizontalAdvance(text) // 2
                fb_painter.setPen(QPen(self._text_color))
                if self._analog_face_shadow:
                    tz_shadow_offset = 3 if self._analog_shadow_intense else 2
                    tz_shadow_color = QColor(0, 0, 0, _scaled_alpha(max(60, int(self._text_color.alpha() * 0.45))))
                    fb_painter.setPen(QPen(tz_shadow_color))
                    fb_painter.drawText(tz_x + tz_shadow_offset, tz_y + tz_shadow_offset, text)
                fb_painter.setPen(QPen(self._text_color))
                fb_painter.drawText(tz_x, tz_y, text)
        finally:
            fb_painter.end()

        # Blit the composited frame buffer to the widget
        painter = QPainter(self)
        try:
            # Ensure we repaint the entire widget, not just the update region,
            # so old hand shadows cannot accumulate outside Qt's clip.
            painter.setClipRect(self.rect(), Qt.ClipOperation.ReplaceClip)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
            painter.drawPixmap(0, 0, frame_buffer)
        finally:
            painter.end()

    def _acquire_analog_frame_buffer(self, width: int, height: int, dpr: float) -> QPixmap:
        """Return a reusable frame buffer pixmap for analog paints."""
        buffer = self._analog_frame_buffer
        needs_new = (
            buffer is None
            or self._analog_frame_buffer_size != (width, height)
            or self._analog_frame_buffer_dpr is None
            or not math.isclose(self._analog_frame_buffer_dpr, dpr, rel_tol=1e-6)
        )
        if needs_new:
            buffer = QPixmap(max(1, int(width * dpr)), max(1, int(height * dpr)))
            buffer.setDevicePixelRatio(max(1.0, dpr))
            self._analog_frame_buffer = buffer
            self._analog_frame_buffer_size = (width, height)
            self._analog_frame_buffer_dpr = float(dpr)
        return buffer

    def _compute_analog_padding(self) -> tuple[int, int, int, int]:
        dpi_y = max(96, int(round(self.logicalDpiY()))) if hasattr(self, "logicalDpiY") else 96
        vertical_padding = max(12, int(round(15 * dpi_y / 96.0)))
        horizontal_padding = vertical_padding
        tz_font_size = max(8, self._font_size // 3)
        bottom_margin = vertical_padding
        if self._show_timezone:
            bottom_margin += tz_font_size + max(4, vertical_padding // 2)
        return horizontal_padding, vertical_padding, bottom_margin, tz_font_size

    def _compute_analog_visual_offset(self) -> tuple[int, int]:
        """Calculate the offset from widget bounds to the visual top-left of the clock.
        
        When the analogue clock has no background, the widget bounds include padding.
        This method calculates where the visual content actually appears:
        - With numerals: offset to XII numeral position
        - Without numerals: offset to clock face edge
        
        Returns:
            (x_offset, y_offset): Distance from widget (0,0) to visual clock edge
        """
        if self._display_mode != "analog" or self._show_background:
            return (0, 0)
        
        # Get the adjusted rect used for painting
        left_pad, top_pad, bottom_margin, _ = self._compute_analog_padding()
        widget_rect = self.rect()
        rect = widget_rect.adjusted(left_pad, top_pad, -left_pad, -bottom_margin)
        side = min(rect.width(), rect.height())
        if side <= 0:
            return (0, 0)
        
        center_x = rect.x() + rect.width() // 2
        center_y = rect.y() + rect.height() // 2
        
        # If numerals are hidden, the clock face itself is the visual boundary
        if not self._show_numerals:
            # Calculate radius without numeral clearance
            radius = side // 2
            # Visual boundary is at the clock face edge
            visual_top = center_y - radius
            visual_left = center_x - radius
            return (max(0, visual_left), max(0, visual_top))
        
        # With numerals: calculate offset to numeral positions
        # Calculate numeral metrics (same as in paintEvent)
        numeral_pt = max(8, min(int(self._font_size * 0.25), max(9, side // 18)))
        from PySide6.QtGui import QFontMetrics, QFont
        numeral_font = QFont(self._font_family, numeral_pt, QFont.Weight.Bold)
        numeral_metrics = QFontMetrics(numeral_font)
        numeral_height = numeral_metrics.height()
        
        # Calculate radius and numeral radius (same as in paintEvent)
        numeral_clearance = numeral_height + max(6, numeral_height // 3)
        radius = side // 2 - numeral_clearance
        if radius <= 0:
            return (0, 0)
        
        numeral_pull_in = max(2, numeral_height // 3) - 5
        numeral_radius = radius + numeral_height - numeral_pull_in
        
        # XII numeral is at angle -90°, so ty = center_y - numeral_radius
        # Text is drawn at ty + th // 4, so top of text is at ty - th * 0.75
        visual_top = center_y - numeral_radius - int(numeral_height * 0.75)
        
        # IX numeral is at angle 180°, so tx = center_x - numeral_radius
        # Text is drawn centered, so left edge is at tx - tw/2
        # For simplicity, use numeral_radius as the visual left offset
        visual_left = center_x - numeral_radius - numeral_height // 2
        
        return (max(0, visual_left), max(0, visual_top))
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up clock widget")
        self.stop()
        if self._tz_label:
            self._tz_label.deleteLater()
            self._tz_label = None
