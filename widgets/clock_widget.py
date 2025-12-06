"""
Clock widget for screensaver overlay.

Displays current time with configurable format, position, and styling.
"""
from typing import Optional, Union, Dict, Any
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
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QPaintEvent
from shiboken6 import Shiboken

from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile, configure_overlay_widget_attributes
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from core.logging.logger import get_logger

logger = get_logger(__name__)


class TimeFormat(Enum):
    """Time format options."""
    TWELVE_HOUR = "12h"
    TWENTY_FOUR_HOUR = "24h"


class ClockPosition(Enum):
    """Clock position on screen."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    TOP_CENTER = "top_center"
    BOTTOM_CENTER = "bottom_center"
    CENTER = "center"


class ClockWidget(QLabel):
    """
    Clock widget for displaying time on screensaver.
    
    Features:
    - 12h/24h format
    - Configurable position
    - Auto-update every second
    - Customizable font and colors
    - Show/hide seconds
    """
    
    # Signals
    time_updated = Signal(str)  # Emits formatted time string
    
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
        super().__init__(parent)
        
        self._time_format = time_format
        self._position = position
        self._show_seconds = show_seconds
        self._show_timezone = show_timezone
        self._timer: Optional[QTimer] = None
        self._timer_handle: Optional[OverlayTimerHandle] = None
        self._enabled = False
        
        # Separate label for timezone
        self._tz_label: Optional[QLabel] = None
        
        # Timezone setup
        self._timezone_str = timezone_str
        self._timezone = self._parse_timezone(timezone_str)
        self._timezone_abbrev = self._get_timezone_abbrev()
        
        # Styling defaults
        self._font_family = "Segoe UI"
        self._font_size = 48
        self._text_color = QColor(255, 255, 255, 230)  # White with slight transparency
        self._margin = 20  # Margin from edge
        
        # Background frame settings
        self._show_background = False
        self._bg_opacity = 0.9  # 90% opacity default
        self._bg_color = QColor(64, 64, 64, int(255 * self._bg_opacity))  # Dark grey
        self._bg_border_width = 2
        self._bg_border_color = QColor(128, 128, 128, 200)  # Light grey border
        # Display mode: digital (default) or analogue clock-face rendering.
        self._display_mode: str = "digital"
        self._show_numerals: bool = True
        # Optional analogue-only drop shadow under the clock face and hands.
        self._analog_face_shadow: bool = True

        # Last timestamp used for analogue rendering.
        self._current_dt: Optional[datetime] = None
        self._shadow_config: Optional[Dict[str, Any]] = None
        self._has_faded_in: bool = False
        self._overlay_name: str = "clock"
        
        # Setup widget
        self._setup_ui()
        
        logger.debug(f"ClockWidget created (format={time_format.value}, "
                    f"position={position.value}, seconds={show_seconds}, "
                    f"timezone={timezone_str}, show_tz={show_timezone})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        # Configure attributes to prevent flicker with GL compositor
        configure_overlay_widget_attributes(self)
        
        # Set label properties
        self.setObjectName("clock_main")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_stylesheet()
        
        # Set font
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
        # Create timezone label if needed
        if self._show_timezone and self.parent():
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
        
        # Initially hidden
        self.hide()
    
    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        self._shadow_config = config

    def set_overlay_name(self, name: str) -> None:
        self._overlay_name = str(name) or "clock"
    
    def start(self) -> None:
        """Start clock updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Clock already running")
            return
        
        # Update immediately
        self._update_time()

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
            self._start_widget_fade_in(1500)

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                overlay_name = getattr(self, "_overlay_name", "clock")
                parent.request_overlay_fade_sync(overlay_name, _starter)
            except Exception:
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
            except Exception:
                pass
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
        if duration_ms <= 0:
            try:
                self.show()
            except Exception:
                pass
            if self._tz_label:
                try:
                    self._tz_label.show()
                    self._tz_label.raise_()
                except Exception:
                    pass
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                pass
            self._has_faded_in = True
            return

        if self.parent():
            try:
                self._update_position()
            except Exception:
                pass

        try:
            self.show()
        except Exception:
            pass
        if self._tz_label:
            try:
                self._tz_label.show()
                self._tz_label.raise_()
            except Exception:
                pass

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            try:
                apply_widget_shadow(
                    self,
                    self._shadow_config or {},
                    has_background_frame=self._show_background,
                )
            except Exception:
                pass
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
                    except Exception:
                        pass
                    self._timer_handle = None  # type: ignore[assignment]

                if getattr(self, "_timer", None) is not None:
                    try:
                        self._timer.stop()  # type: ignore[union-attr]
                        self._timer.deleteLater()  # type: ignore[union-attr]
                    except Exception:
                        pass
                    self._timer = None  # type: ignore[assignment]

                self._enabled = False
                return
        except Exception:
            return

        # Get current time in specified timezone
        if self._timezone is None:
            now = datetime.now()
        else:
            now = datetime.now(self._timezone)

        self._current_dt = now

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
                except Exception:
                    pass
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

        # Request a repaint for analogue mode so hands tick smoothly.
        if self._display_mode == "analog":
            self.update()
    
    def _update_position(self) -> None:
        """Update widget position based on settings."""
        if not self.parent():
            return
        
        parent_width = self.parent().width()
        parent_height = self.parent().height()
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate position with 20px minimum margin from all edges
        edge_margin = 20
        if self._position == ClockPosition.TOP_LEFT:
            x = edge_margin
            y = edge_margin
        elif self._position == ClockPosition.TOP_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = edge_margin
        elif self._position == ClockPosition.BOTTOM_LEFT:
            x = edge_margin
            y = parent_height - widget_height - edge_margin
        elif self._position == ClockPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = parent_height - widget_height - edge_margin
        elif self._position == ClockPosition.TOP_CENTER:
            x = (parent_width - widget_width) // 2
            y = edge_margin
        elif self._position == ClockPosition.BOTTOM_CENTER:
            x = (parent_width - widget_width) // 2
            y = parent_height - widget_height - edge_margin
        elif self._position == ClockPosition.CENTER:
            x = (parent_width - widget_width) // 2
            y = (parent_height - widget_height) // 2
        else:
            x = edge_margin
            y = edge_margin
        
        self.move(x, y)
        
        # Position timezone label inside the background frame (bottom-right)
        if self._show_timezone and self._tz_label:
            tz_x = self.width() - self._tz_label.width() - 12
            tz_y = self.height() - self._tz_label.height() - 6
            self._tz_label.move(tz_x, tz_y)
    
    def set_time_format(self, time_format: TimeFormat) -> None:
        """
        Set time format.
        
        Args:
            time_format: 12h or 24h format
        """
        self._time_format = time_format
        
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
    
    def set_position(self, position: ClockPosition) -> None:
        """
        Set clock position.
        
        Args:
            position: Screen position
        """
        self._position = position
        
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
            self.update()

    def set_analog_face_shadow(self, enabled: bool) -> None:
        """Enable or disable the analogue face/hand drop shadow effect."""

        self._analog_face_shadow = bool(enabled)
        if self._display_mode == "analog":
            self.update()

    def set_font_family(self, family: str) -> None:
        """
        Set font family.
        
        Args:
            family: Font family name
        """
        self._font_family = family
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
        # Update timezone label font if it exists
        if self._tz_label:
            tz_font_size = max(int(self._font_size / 4), 8)
            tz_font = QFont(self._font_family, tz_font_size)
            self._tz_label.setFont(tz_font)
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def set_font_size(self, size: int) -> None:
        """
        Set font size.
        
        Args:
            size: Font size in points
        """
        if size <= 0:
            logger.warning(f"[FALLBACK] Invalid font size {size}, using 48")
            size = 48
        
        self._font_size = size
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
        # Update timezone label font if it exists
        if self._tz_label:
            tz_font_size = max(int(self._font_size / 4), 8)
            tz_font = QFont(self._font_family, tz_font_size)
            self._tz_label.setFont(tz_font)
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def set_text_color(self, color: QColor) -> None:
        """
        Set text color.
        
        Args:
            color: Text color
        """
        self._text_color = color
        self._update_stylesheet()
    
    def set_margin(self, margin: int) -> None:
        """
        Set margin from screen edges.
        
        Args:
            margin: Margin in pixels
        """
        if margin < 0:
            logger.warning(f"[FALLBACK] Invalid margin {margin}, using 20")
            margin = 20
        
        self._margin = margin
        
        # Update position immediately if running
        if self._enabled:
            self._update_position()
    
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
    
    def set_show_background(self, show: bool) -> None:
        """
        Set whether to show background frame.
        
        Args:
            show: True to show background frame
        """
        self._show_background = show
        self._update_stylesheet()
    
    def set_background_color(self, color: QColor) -> None:
        """
        Set background frame color.
        
        Args:
            color: Background color (with alpha for opacity)
        """
        self._bg_color = color
        if self._show_background:
            self._update_stylesheet()
    
    def set_background_opacity(self, opacity: float) -> None:
        """
        Set background frame opacity (0.0 to 1.0).
        
        Args:
            opacity: Opacity value from 0.0 (transparent) to 1.0 (opaque)
        """
        self._bg_opacity = max(0.0, min(1.0, opacity))
        # Update background color with new opacity
        self._bg_color.setAlpha(int(255 * self._bg_opacity))
        if self._show_background:
            self._update_stylesheet()
    
    def set_background_border(self, width: int, color: QColor) -> None:
        """
        Set background frame border.
        
        Args:
            width: Border width in pixels
            color: Border color
        """
        self._bg_border_width = width
        self._bg_border_color = color
        if self._show_background:
            self._update_stylesheet()
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        if self._show_background:
            # Extend bottom padding if timezone is shown to include it in the frame
            bottom_padding = 6
            if self._show_timezone and self._tz_label:
                try:
                    self._tz_label.adjustSize()
                    bottom_padding = max(6, self._tz_label.height() + 6)
                except Exception:
                    bottom_padding = 20
            # With background frame
            self.setStyleSheet(f"""
                QLabel#clock_main {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()}, 
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()}, 
                                                                 {self._bg_border_color.green()}, 
                                                                 {self._bg_border_color.blue()}, 
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                    padding: 6px 12px {bottom_padding}px 16px;
                }}
            """)
        else:
            # Transparent background (default)
            self.setStyleSheet(f"""
                QLabel#clock_main {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    padding: 6px 12px 6px 16px;
                }}
            """)
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom paint for analogue mode; fall back to QLabel for digital."""

        if self._display_mode != "analog":
            super().paintEvent(event)
            return

        # First let QLabel render its background/frame (via stylesheet), but
        # with an empty text payload.
        super().paintEvent(event)

        if self._current_dt is None:
            if self._timezone is None:
                now = datetime.now()
            else:
                now = datetime.now(self._timezone)
        else:
            now = self._current_dt

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Leave a generous outer margin, with extra space at the bottom for
        # the timezone abbreviation.
        rect = self.rect().adjusted(16, 16, -16, -36)
        side = min(rect.width(), rect.height())
        if side <= 0:
            return

        center_x = rect.x() + rect.width() // 2
        center_y = rect.y() + rect.height() // 2

        # Precompute numeral metrics so we can keep the face well inside
        # the widget and place numerals just outside the circle. Numeral
        # size is scaled from both the configured font size and the
        # available side length so they stay readable but subtle. This
        # keeps them smaller than the main time text and avoids crowding
        # the clock face.
        numeral_pt = max(8, min(int(self._font_size * 0.25), max(9, side // 18)))
        numeral_font = QFont(self._font_family, numeral_pt)
        painter.setFont(numeral_font)
        numeral_metrics = painter.fontMetrics()
        numeral_height = numeral_metrics.height()

        # Pull the clock face further in from the widget edges so there is
        # comfortable space for numerals plus a bit of padding.
        radius = side // 2 - (numeral_height * 2) - 8
        if radius <= 0:
            return

        # Optional subtle drop shadow under the analogue clock face.
        if self._analog_face_shadow:
            shadow_color = QColor(0, 0, 0, max(75, self._text_color.alpha() // 3))
            shadow_pen = QPen(shadow_color)
            shadow_pen.setWidth(2)
            painter.setPen(shadow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                center_x - radius + 2,
                center_y - radius + 2,
                radius * 2,
                radius * 2,
            )

        # Clock face border
        face_pen = QPen(self._text_color)
        face_pen.setWidth(2)
        painter.setPen(face_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Hour markers
        marker_len = max(6, radius // 10)
        for i in range(12):
            angle = math.radians((i / 12.0) * 360.0 - 90.0)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            outer_x = center_x + int(cos_a * (radius - 2))
            outer_y = center_y + int(sin_a * (radius - 2))
            inner_x = center_x + int(cos_a * (radius - marker_len - 2))
            inner_y = center_y + int(sin_a * (radius - marker_len - 2))
            painter.drawLine(inner_x, inner_y, outer_x, outer_y)

        # Optional numerals (I–XII) placed just outside the clock face.
        if self._show_numerals:
            roman_map = {
                1: "I",
                2: "II",
                3: "III",
                4: "IV",
                5: "V",
                6: "VI",
                7: "VII",
                8: "VIII",
                9: "IX",
                10: "X",
                11: "XI",
                12: "XII",
            }

            # Place numerals with a clear gap from the face so they never
            # visually touch the circle or its hour markers.
            numeral_radius = radius + numeral_height
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

                # Subtle drop shadow for numerals, matching the analogue
                # face/hand shadow so the entire dial reads as a single
                # lit element.
                if self._analog_face_shadow:
                    numeral_shadow = QColor(0, 0, 0, max(65, self._text_color.alpha() // 3))
                    painter.setPen(QPen(numeral_shadow))
                    painter.drawText(tx - tw // 2 + 1, ty + th // 4 + 1, text)

                painter.setPen(QPen(self._text_color))
                painter.drawText(tx - tw // 2, ty + th // 4, text)

        # Helper to draw a hand with a subtle bottom-right shadow.
        def _draw_hand(angle_deg: float, length: float, thickness: int) -> None:
            angle = math.radians(angle_deg - 90.0)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            ex = center_x + int(cos_a * length)
            ey = center_y + int(sin_a * length)

            if self._analog_face_shadow:
                shadow_color = QColor(0, 0, 0, max(55, self._text_color.alpha() // 3))
                shadow_pen = QPen(shadow_color)
                shadow_pen.setWidth(thickness)
                painter.setPen(shadow_pen)
                painter.drawLine(center_x + 2, center_y + 2, ex + 2, ey + 2)

            hand_pen = QPen(self._text_color)
            hand_pen.setWidth(thickness)
            painter.setPen(hand_pen)
            painter.drawLine(center_x, center_y, ex, ey)

        # Compute hand angles
        sec = now.second + now.microsecond / 1_000_000.0
        minute = now.minute + sec / 60.0
        hour = (now.hour % 12) + minute / 60.0

        hour_angle = (hour / 12.0) * 360.0
        minute_angle = (minute / 60.0) * 360.0
        second_angle = (sec / 60.0) * 360.0

        # Draw hour and minute hands
        _draw_hand(hour_angle, radius * 0.5, max(3, radius // 15))
        _draw_hand(minute_angle, radius * 0.75, max(2, radius // 20))

        # Optional seconds hand (thinner and longer)
        if self._show_seconds:
            _draw_hand(second_angle, radius * 0.85, 1)

        # Timezone abbreviation rendered below the analogue clock, centred
        # horizontally with a small gap from the face.
        if self._show_timezone and self._timezone_abbrev:
            tz_font = QFont(self._font_family, max(8, self._font_size // 3))
            painter.setFont(tz_font)
            tz_metrics = painter.fontMetrics()
            tz_height = tz_metrics.height()
            text = self._timezone_abbrev

            # Position the timezone label below both the face and the
            # numerals with extra padding so nothing overlaps visually.
            top_y = center_y + radius + (numeral_height * 2) + 8
            max_top = self.height() - tz_height - 4
            if top_y > max_top:
                top_y = max_top

            painter.drawText(
                0,
                top_y,
                self.width(),
                tz_height,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                text,
            )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up clock widget")
        self.stop()
        if self._tz_label:
            self._tz_label.deleteLater()
            self._tz_label = None
