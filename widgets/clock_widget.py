"""
Clock widget for screensaver overlay.

Displays current time with configurable format, position, and styling.
"""
from typing import Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import time
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont, QColor

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
        
        # Setup widget
        self._setup_ui()
        
        logger.debug(f"ClockWidget created (format={time_format.value}, "
                    f"position={position.value}, seconds={show_seconds}, "
                    f"timezone={timezone_str}, show_tz={show_timezone})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        # Set label properties
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_stylesheet()
        
        # Set font
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
        # Create timezone label if needed
        if self._show_timezone and self.parent():
            self._tz_label = QLabel(self.parent())
            self._tz_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            tz_font_size = max(int(self._font_size / 4), 8)
            tz_font = QFont(self._font_family, tz_font_size)
            self._tz_label.setFont(tz_font)
            self._tz_label.setStyleSheet(f"""QLabel {{
                color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                           {self._text_color.blue()}, {self._text_color.alpha()});
                background-color: transparent;
            }}""")
            self._tz_label.hide()
        
        # Initially hidden
        self.hide()
    
    def start(self) -> None:
        """Start clock updates."""
        if self._enabled:
            logger.warning("[FALLBACK] Clock already running")
            return
        
        # Update immediately
        self._update_time()
        
        # Start timer (update every second)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)  # 1 second
        
        self._enabled = True
        self.show()
        if self._tz_label:
            self._tz_label.show()
            self._tz_label.raise_()
        
        logger.info("Clock widget started")
    
    def stop(self) -> None:
        """Stop clock updates."""
        if not self._enabled:
            return
        
        if self._timer:
            try:
                self._timer.stop()
                self._timer.deleteLater()
            except RuntimeError:
                pass
            self._timer = None
        
        self._enabled = False
        self.hide()
        
        logger.debug("Clock widget stopped")
    
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
        # Get current time in specified timezone
        if self._timezone is None:
            now = datetime.now()
        else:
            now = datetime.now(self._timezone)
        
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
        
        # Plain text display
        self.setText(time_str)
        self.setTextFormat(Qt.TextFormat.PlainText)
        
        # Update timezone label if shown
        if self._show_timezone and self._tz_label and self._timezone_abbrev:
            self._tz_label.setText(self._timezone_abbrev)
            self._tz_label.adjustSize()
        
        # Adjust size to content
        self.adjustSize()
        
        # Update position (includes timezone label positioning)
        if self.parent():
            self._update_position()
        
        # Emit signal
        self.time_updated.emit(time_str)
    
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
        
        # Position timezone label directly below clock with minimal gap
        if self._show_timezone and self._tz_label:
            tz_x = x + widget_width - self._tz_label.width()  # Right-aligned with clock
            tz_y = y + widget_height - 2  # 2px gap (negative overlap)
            self._tz_label.move(tz_x, tz_y)
    
    def set_time_format(self, time_format: TimeFormat) -> None:
        """
        Set time format.
        
        Args:
            time_format: 12h or 24h format
        """
        self._time_format = time_format
        logger.debug(f"Time format set to {time_format.value}")
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def set_position(self, position: ClockPosition) -> None:
        """
        Set clock position.
        
        Args:
            position: Screen position
        """
        self._position = position
        logger.debug(f"Position set to {position.value}")
        
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
        logger.debug(f"Show seconds set to {show_seconds}")
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
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
        
        logger.debug(f"Font family set to {family}")
        
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
        
        logger.debug(f"Font size set to {size}")
        
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
        logger.debug(f"Text color set to rgba({color.red()}, {color.green()}, "
                    f"{color.blue()}, {color.alpha()})")
    
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
        logger.debug(f"Margin set to {margin}px")
        
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
        logger.debug(f"Timezone set to {timezone_str} (abbrev: {self._timezone_abbrev})")
        
        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def set_show_timezone(self, show_timezone: bool) -> None:
        """
        Set whether to display timezone abbreviation.
        
        Args:
            show_timezone: True to show timezone
        """
        self._show_timezone = show_timezone
        logger.debug(f"Show timezone set to {show_timezone}")
        
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
        logger.debug(f"Show background set to {show}")
    
    def set_background_color(self, color: QColor) -> None:
        """
        Set background frame color.
        
        Args:
            color: Background color (with alpha for opacity)
        """
        self._bg_color = color
        if self._show_background:
            self._update_stylesheet()
        logger.debug(f"Background color set to rgba({color.red()}, {color.green()}, "
                    f"{color.blue()}, {color.alpha()})")
    
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
        logger.debug(f"Background opacity set to {self._bg_opacity * 100:.0f}%")
    
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
        logger.debug(f"Background border set to {width}px, rgba({color.red()}, {color.green()}, "
                    f"{color.blue()}, {color.alpha()})")
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        if self._show_background:
            # Extend bottom padding if timezone is shown to include it in the frame
            bottom_padding = 20 if (self._show_timezone and self._tz_label) else 6
            # With background frame
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
                    padding: 6px 12px {bottom_padding}px 16px;
                }}
            """)
        else:
            # Transparent background (default)
            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    padding: 6px 12px 6px 16px;
                }}
            """)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up clock widget")
        self.stop()
        if self._tz_label:
            self._tz_label.deleteLater()
            self._tz_label = None
