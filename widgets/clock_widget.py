"""
Clock widget for screensaver overlay.

Displays current time with configurable format, position, and styling.
"""
from typing import Optional
from datetime import datetime
from enum import Enum
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import QTimer, Qt, QPoint, Signal
from PySide6.QtGui import QFont, QColor, QPalette

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
                 show_seconds: bool = True):
        """
        Initialize clock widget.
        
        Args:
            parent: Parent widget
            time_format: 12h or 24h format
            position: Screen position
            show_seconds: Whether to show seconds
        """
        super().__init__(parent)
        
        self._time_format = time_format
        self._position = position
        self._show_seconds = show_seconds
        self._timer: Optional[QTimer] = None
        self._enabled = False
        
        # Styling defaults
        self._font_family = "Segoe UI"
        self._font_size = 48
        self._text_color = QColor(255, 255, 255, 230)  # White with slight transparency
        self._margin = 20  # Margin from edge
        
        # Setup widget
        self._setup_ui()
        
        logger.debug(f"ClockWidget created (format={time_format.value}, "
                    f"position={position.value}, seconds={show_seconds})")
    
    def _setup_ui(self) -> None:
        """Setup widget UI."""
        # Set label properties
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                           {self._text_color.blue()}, {self._text_color.alpha()});
                background-color: transparent;
                padding: 10px 20px;
            }}
        """)
        
        # Set font
        font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        self.setFont(font)
        
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
    
    def _update_time(self) -> None:
        """Update displayed time."""
        now = datetime.now()
        
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
        
        # Update label
        self.setText(time_str)
        
        # Adjust size to content
        self.adjustSize()
        
        # Update position
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
        
        # Calculate position
        if self._position == ClockPosition.TOP_LEFT:
            x = self._margin
            y = self._margin
        elif self._position == ClockPosition.TOP_RIGHT:
            x = parent_width - widget_width - self._margin
            y = self._margin
        elif self._position == ClockPosition.BOTTOM_LEFT:
            x = self._margin
            y = parent_height - widget_height - self._margin
        elif self._position == ClockPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - self._margin
            y = parent_height - widget_height - self._margin
        elif self._position == ClockPosition.TOP_CENTER:
            x = (parent_width - widget_width) // 2
            y = self._margin
        elif self._position == ClockPosition.BOTTOM_CENTER:
            x = (parent_width - widget_width) // 2
            y = parent_height - widget_height - self._margin
        else:
            x = self._margin
            y = self._margin
        
        self.move(x, y)
    
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
        self.setStyleSheet(f"""
            QLabel {{
                color: rgba({color.red()}, {color.green()}, 
                           {color.blue()}, {color.alpha()});
                background-color: transparent;
                padding: 10px 20px;
            }}
        """)
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
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up clock widget")
        self.stop()
