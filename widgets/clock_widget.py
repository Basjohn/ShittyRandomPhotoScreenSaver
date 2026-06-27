"""
Clock widget for screensaver overlay.

Displays current time with configurable format, position, and styling.
"""
from typing import Optional, Union, TYPE_CHECKING
from dataclasses import dataclass
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
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QFont, QFontMetrics, QColor, QPainter, QPen, QPaintEvent, QPainterPath, QPainterPathStroker, QPixmap
from PySide6.QtCore import QRectF
from shiboken6 import Shiboken

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import ShadowFadeProfile
from widgets.clock_ticker import get_global_clock_ticker
from core.settings.shadow_tuning import CARD_SHADOW_TUNING as PAINTED_FRAME_SHADOW_TUNING
from core.logging.logger import get_logger
from core.performance import widget_paint_sample
from rendering.custom_layout_contract import (
    clamp_local_rect_to_bounds,
    get_screen_layout_entries_for_screen,
    load_custom_layout_map,
    normalize_local_rect,
    write_custom_layout_map,
)

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
    DIGITAL_MIN_SIDE_PAD = 8
    DIGITAL_MAX_SIDE_PAD = 14
    DIGITAL_MIN_TOP_PAD = 4
    DIGITAL_MAX_TOP_PAD = 8
    DIGITAL_BOTTOM_PAD = 6
    DIGITAL_TZ_UPPER_SLACK_RATIO = 0.25
    ANALOG_NUMERAL_SCALE = 0.80
    ANALOG_CARD_RING_SCALE = 1.30
    ANALOG_FRAMED_NUMERAL_SCALE = 0.72
    ANALOG_FRAMED_CARD_RING_SCALE = 1.74
    ANALOG_FRAMED_TIMEZONE_SCALE = 0.80
    ANALOG_FRAMED_TIMEZONE_GAP_PX = 33
    ANALOG_UNFRAMED_TIMEZONE_GAP_PX = 20
    ANALOG_NUMERAL_RADIAL_COMPRESS = 0.02

    @dataclass(frozen=True)
    class _AnalogNumeralPlacement:
        radial_offset_em: float = 0.0
        tangential_offset_em: float = 0.0
    
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
        self._effective_digital_font_size: int = self._font_size

        # Last timestamp used for analogue rendering.
        self._current_dt: Optional[datetime] = None
        
        # Static element cache for analog clock face (circle, markers, numerals)
        # Only hands need to be redrawn each second
        self._cached_clock_face: Optional["QPixmap"] = None
        self._cached_clock_face_size: Optional[tuple[int, int]] = None
        self._clock_face_cache_invalidated: bool = True
        self._analog_frame_buffer: Optional["QPixmap"] = None
        self._analog_frame_buffer_size: Optional[tuple[int, int]] = None
        
        # Setup widget
        self._setup_ui()
        
        # Track if we've been initialized via lifecycle
        self._lifecycle_initialized = False
        
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

    def _set_main_clock_font(self, point_size: int) -> None:
        font = QFont(self._font_family, max(8, int(point_size)), QFont.Weight.Bold)
        if self._display_mode != "analog":
            try:
                font.setFeature(QFont.Tag.fromString("tnum"), 1)
            except Exception:
                logger.debug("[CLOCK] Failed to enable tabular numerals", exc_info=True)
        self.setFont(font)

    def _digital_measurement_text(self) -> str:
        if self._time_format == TimeFormat.TWELVE_HOUR:
            return "11:59:59 PM" if self._show_seconds else "11:59 PM"
        return "23:59:59" if self._show_seconds else "23:59"

    def _compute_digital_padding(self, tz_label_height: int | None = None) -> tuple[int, int, int, int]:
        side_pad = max(
            self.DIGITAL_MIN_SIDE_PAD,
            min(self.DIGITAL_MAX_SIDE_PAD, int(round(self._font_size * 0.16))),
        )
        top_pad = max(
            self.DIGITAL_MIN_TOP_PAD,
            min(self.DIGITAL_MAX_TOP_PAD, int(round(self._font_size * 0.10))),
        )
        bottom_pad = self.DIGITAL_BOTTOM_PAD
        if self._show_timezone and self._display_mode != "analog":
            label_height = tz_label_height if tz_label_height is not None else self._get_tz_label_height_estimate()
            bottom_pad += self.DIGITAL_TZ_GAP + max(0, int(label_height))
        return side_pad, top_pad, side_pad, bottom_pad

    def _fit_digital_font_to_bounds(self) -> int:
        if self._display_mode == "analog":
            self._effective_digital_font_size = self._font_size
            return self._font_size

        sample_text = self._digital_measurement_text()
        sample_size = self._get_tz_label_height_estimate() if self._show_timezone else 0
        left_pad, top_pad, right_pad, bottom_pad = self._compute_digital_padding(sample_size)
        available_width = max(1, self.width() - left_pad - right_pad)
        available_height = max(1, self.height() - top_pad - bottom_pad)

        best_size = max(8, int(self._font_size))
        for candidate in range(best_size, 7, -1):
            metrics = QFontMetrics(QFont(self._font_family, candidate, QFont.Weight.Bold))
            if (
                metrics.horizontalAdvance(sample_text) <= available_width
                and metrics.height() <= available_height
            ):
                best_size = candidate
                break

        self._effective_digital_font_size = best_size
        return best_size

    def _apply_digital_font_fit(self) -> None:
        target_size = self._fit_digital_font_to_bounds()
        self._set_main_clock_font(target_size)
        self._update_tz_label_font()

    def _natural_custom_size_for_mode(self, mode: str) -> QSize:
        target = str(mode or "").lower()
        font_size = max(12, int(self._font_size))
        if target == "analog":
            width = max(160, int(round(font_size * 4.5)))
            height_factor = 1.3 if self._show_timezone else 1.0
            height = max(width, int(round(width * height_factor)))
            return QSize(width, height)

        sample_text = self._digital_measurement_text()
        digital_font = QFont(self._font_family, font_size, QFont.Weight.Bold)
        try:
            digital_font.setFeature(QFont.Tag.fromString("tnum"), 1)
        except Exception:
            logger.debug("[CLOCK] Failed to enable tabular numerals for natural size", exc_info=True)
        metrics = QFontMetrics(digital_font)

        tz_label_height = 0
        if self._show_timezone:
            tz_font_size = max(int(font_size / 4), 8)
            tz_metrics = QFontMetrics(QFont(self._font_family, tz_font_size, QFont.Weight.Bold))
            tz_text = self._timezone_abbrev or "SAST"
            tz_rect = tz_metrics.tightBoundingRect(tz_text)
            if tz_rect.isNull():
                tz_rect = tz_metrics.boundingRect(tz_text)
            tz_label_height = max(tz_metrics.height(), tz_rect.height())

        left_pad, top_pad, right_pad, bottom_pad = self._compute_digital_padding(tz_label_height)
        width = max(
            160,
            int(math.ceil(metrics.horizontalAdvance(sample_text) + left_pad + right_pad)),
        )
        height = max(
            72,
            int(math.ceil(metrics.height() + top_pad + bottom_pad)),
        )
        return QSize(width, height)

    def _rebuild_custom_rect_for_mode(self, target_mode: str) -> QRect | None:
        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return None
        parent = self.parentWidget()
        if parent is None:
            return None

        target_size = self._natural_custom_size_for_mode(target_mode)
        center_x = custom_rect.x() + (custom_rect.width() / 2.0)
        center_y = custom_rect.y() + (custom_rect.height() / 2.0)
        rebuilt = QRect(
            int(round(center_x - (target_size.width() / 2.0))),
            int(round(center_y - (target_size.height() / 2.0))),
            int(target_size.width()),
            int(target_size.height()),
        )
        return clamp_local_rect_to_bounds(rebuilt, parent.size())

    def _position_timezone_label(self) -> None:
        if not self._show_timezone or self._tz_label is None:
            return
        if self._display_mode == "analog":
            tz_x = self.width() - self._tz_label.width() - 18
            tz_y = self.height() - self._tz_label.height() + 4
        else:
            _, _, _, bottom_pad = self._compute_digital_padding(self._tz_label.height())
            tz_x = max(0, int((self.width() - self._tz_label.width()) / 2))
            reserved_top = max(0, self.height() - bottom_pad)
            reserved_height = max(self._tz_label.height(), self.height() - reserved_top)
            available_slack = max(0, reserved_height - self._tz_label.height())
            top_slack = int(round(available_slack * self.DIGITAL_TZ_UPPER_SLACK_RATIO))
            tz_y = reserved_top + max(0, top_slack)
        self._tz_label.move(tz_x, tz_y)

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
        """Activate clock - subscribe to global ticker and show widget (lifecycle hook)."""
        if not self._ensure_thread_manager("ClockWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
        # Update immediately
        self._update_time()
        
        # Subscribe to global clock ticker (shared across all clock widgets)
        ticker = get_global_clock_ticker()
        ticker.set_thread_manager(self._thread_manager)
        ticker.subscribe(self._update_time)
        
        # Start fade-in
        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                overlay_name = getattr(self, "_overlay_name", "clock")
                parent.request_overlay_fade_sync(overlay_name, self._start_widget_fade_in)
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
                self._start_widget_fade_in()
        else:
            self._start_widget_fade_in()
        
        logger.debug("[LIFECYCLE] ClockWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate clock - unsubscribe from global ticker (lifecycle hook)."""
        # Unsubscribe from global clock ticker
        ticker = get_global_clock_ticker()
        ticker.unsubscribe(self._update_time)
        
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
        """Start clock updates using shared global ticker."""
        if self._enabled:
            logger.warning("[FALLBACK] Clock already running")
            return
        if not self._ensure_thread_manager("ClockWidget.start"):
            return
        
        # Update immediately
        self._update_time()

        # Subscribe to global clock ticker (shared across all clock widgets)
        ticker = get_global_clock_ticker()
        ticker.set_thread_manager(self._thread_manager)
        ticker.subscribe(self._update_time)

        self._enabled = True
        parent = self.parent()

        def _starter() -> None:
            # Guard against widget being deleted before deferred callback runs
            if not Shiboken.isValid(self):
                return
            self._start_widget_fade_in()

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
        
        # Unsubscribe from global clock ticker
        ticker = get_global_clock_ticker()
        ticker.unsubscribe(self._update_time)
        
        self._enabled = False
        self.hide()
        
        logger.debug("Clock widget stopped")
    
    def _start_widget_fade_in(self, duration_ms: Optional[int] = None) -> None:
        # Guard against widget being deleted before this method runs
        if not Shiboken.isValid(self):
            return

        resolved_duration_ms = (
            ShadowFadeProfile.default_duration_ms()
            if duration_ms is None
            else max(0, int(duration_ms))
        )

        if resolved_duration_ms <= 0:
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
            self._has_faded_in = True
            return

        if Shiboken.isValid(self) and self.parent():
            try:
                self._update_position()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)
        if self._tz_label:
            try:
                self._tz_label.show()
                self._tz_label.raise_()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                duration_ms=resolved_duration_ms,
                has_background_frame=self._show_background,
            )
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
        if self._display_mode != "analog":
            self._apply_digital_font_fit()

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
            self._position_timezone_label()
        # Digital/analog frame styling is setting-driven, not time-driven.
        # Rebuilding the stylesheet every tick can perturb QLabel layout hints
        # in fixed CUSTOM rects and reintroduce second-by-second wobble.
        
        # Note: No need for adjustSize() or _update_position() here - 
        # clock dimensions only change when font/size settings change, not every second.
        # These are now called only when settings actually change (set_font_size, etc.)
        
        # Emit signal
        self.time_updated.emit(time_str)

        # For analog mode, explicitly trigger repaint since setText("") doesn't
        # cause Qt to automatically repaint, and hands need to redraw each second
        if self._display_mode == "analog":
            self.update()
    
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
        self._position_timezone_label()
    
    def set_time_format(self, time_format: TimeFormat) -> None:
        """
        Set time format.
        
        Args:
            time_format: 12h or 24h format
        """
        self._time_format = time_format
        
        # Update stylesheet to tighten padding when timezone hidden
        self._update_stylesheet()
        if self._display_mode != "analog":
            self._apply_digital_font_fit()
            self._position_timezone_label()

        # Update display immediately if running
        if self._enabled:
            self._update_time()

    def set_show_background(self, show: bool) -> None:
        super().set_show_background(show)
        if self._display_mode != "analog":
            self._apply_digital_font_fit()
            self._position_timezone_label()

    def set_widget_manager(self, wm) -> None:
        """Store WidgetManager reference for settings persistence."""
        self._widget_manager = wm

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Toggles digital/analog mode."""
        del local_pos
        new_mode = "digital" if self._display_mode == "analog" else "analog"
        rebuilt_custom_rect = self._rebuild_custom_rect_for_mode(new_mode)
        if rebuilt_custom_rect is not None:
            self._custom_layout_local_rect = QRect(rebuilt_custom_rect)
        self.set_display_mode(new_mode)
        if rebuilt_custom_rect is not None:
            self._apply_custom_layout_size_constraints_if_active()
            self.setGeometry(rebuilt_custom_rect)
        self._persist_display_mode_to_settings(new_mode)
        logger.debug("[CLOCK] Double-click toggled display mode to %s", new_mode)
        return True

    def _persist_display_mode_to_settings(self, new_mode: str) -> None:
        wm = getattr(self, '_widget_manager', None)
        if wm is not None:
            sm = getattr(wm, '_settings_manager', None)
            if sm is not None:
                try:
                    cfg = sm.get_widgets_map() if hasattr(sm, "get_widgets_map") else (sm.get('widgets', {}) or {})
                    if not isinstance(cfg, dict):
                        cfg = {}
                    widget_id = str(getattr(self, "_overlay_name", "clock") or "clock")
                    clock_cfg = cfg.get(widget_id, {}) or {}
                    clock_cfg['clock_analog_mode'] = (new_mode == "analog")
                    clock_cfg['display_mode'] = new_mode
                    cfg[widget_id] = clock_cfg
                    self._persist_display_mode_to_custom_layout(cfg, widget_id, new_mode)
                    if hasattr(sm, "set_widgets_map"):
                        try:
                            sm.set_widgets_map(cfg, emit_change=False)
                        except TypeError:
                            sm.set_widgets_map(cfg)
                    else:
                        sm.set('widgets', cfg)
                    save = getattr(sm, "save", None)
                    if callable(save):
                        save()
                except Exception:
                    logger.debug("[CLOCK] Failed to persist display mode", exc_info=True)

    def _persist_display_mode_to_custom_layout(self, widgets_map: dict, widget_id: str, new_mode: str) -> None:
        custom_rect = getattr(self, "_custom_layout_local_rect", None)
        if not isinstance(custom_rect, QRect):
            return
        parent = self.parentWidget()
        screen = getattr(parent, "_screen", None) if parent is not None else None
        if screen is None:
            try:
                screen = self.screen()
            except Exception:
                screen = None
        if screen is None:
            return
        custom_layout_map = load_custom_layout_map(widgets_map)
        matched_signature, _entries = get_screen_layout_entries_for_screen(custom_layout_map, screen)
        displays = custom_layout_map.get("displays", {})
        candidate_layouts: list[dict] = []
        if matched_signature:
            matched_layout = displays.get(matched_signature)
            if isinstance(matched_layout, dict):
                candidate_layouts.append(matched_layout)
        if not candidate_layouts:
            for layouts in displays.values():
                if isinstance(layouts, dict) and widget_id in layouts:
                    candidate_layouts.append(layouts)
        if len(candidate_layouts) != 1:
            return
        entry = candidate_layouts[0].get(widget_id)
        if not isinstance(entry, dict):
            return
        payload = dict(entry.get("size_payload", {}) or {})
        payload["display_mode"] = new_mode
        payload["font_size"] = int(getattr(self, "_font_size", payload.get("font_size", self.DEFAULT_FONT_SIZE)))
        entry["size_payload"] = payload
        parent = self.parentWidget()
        if parent is not None:
            entry["rect"] = normalize_local_rect(custom_rect, parent.size()).to_mapping()
        candidate_layouts[0][widget_id] = entry
        write_custom_layout_map(widgets_map, custom_layout_map)

    def set_display_mode(self, mode: str) -> None:
        """Set display mode ("digital" or "analog")."""

        mode_l = str(mode).lower()
        if mode_l not in ("digital", "analog"):
            mode_l = "digital"
        if self._display_mode == mode_l:
            return
        self._display_mode = mode_l

        self._apply_display_mode_size_constraints()
        if self._display_mode != "analog":
            self._apply_digital_font_fit()
        else:
            self._set_main_clock_font(self._font_size)

        # Rebuild stylesheet for new mode (padding differs between digital/analog)
        self._update_stylesheet()
        # Invalidate analog cache so first paint is clean
        self._invalidate_clock_face_cache()

        if self._enabled:
            self._update_time()
        else:
            self.update()

        # Resize card and reposition after mode switch
        try:
            self.adjustSize()
        except Exception as e:
            logger.debug("[CLOCK] Exception suppressed: %s", e)
        if self.parent():
            try:
                self._update_position()
            except Exception as e:
                logger.debug("[CLOCK] Exception suppressed: %s", e)

    def _apply_display_mode_size_constraints(self) -> None:
        """Keep the widget footprint contract aligned with the current display mode.

        Analogue clocks derive their face geometry from the live widget rect, so
        any later font-size change must also refresh the minimum footprint.
        Otherwise CUSTOM resize can shrink the numerals while the underlying
        clock face refuses to contract to the same scale.
        """
        if self._display_mode == "analog":
            base_side = max(160, int(self._font_size * 4.5))
            self.setMinimumWidth(base_side)
            self.setMinimumHeight(int(base_side * 1.3))
            return
        self.setMinimumSize(0, 0)
    
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

    def set_font_family(self, family: str) -> None:
        """Set font family - override to use bold weight and update tz label."""
        super().set_font_family(family)
        if self._display_mode == "analog":
            self._set_main_clock_font(self._font_size)
        else:
            self._apply_digital_font_fit()
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
        self._apply_display_mode_size_constraints()
        if self._display_mode == "analog":
            self._set_main_clock_font(self._font_size)
        else:
            self._apply_digital_font_fit()
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
            base_size = self._font_size if self._display_mode == "analog" else self._effective_digital_font_size
            tz_font_size = max(int(base_size / 4), 8)
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
        if self._display_mode != "analog":
            self._apply_digital_font_fit()

        if show_timezone and self._tz_label is None and self.parent():
            # Lazily create timezone label if needed
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
        elif not show_timezone and self._tz_label:
            self._tz_label.hide()

        self._position_timezone_label()

        # Update display immediately if running
        if self._enabled:
            self._update_time()
    
    def _update_stylesheet(self) -> None:
        """Update widget stylesheet based on current settings."""
        if self.uses_painted_frame_shadow():
            if self._display_mode == "analog":
                padding_left, padding_top, padding_bottom, _ = self._compute_analog_padding()
                padding_right = padding_left
                padding_rule = f"{padding_top}px {padding_right}px {padding_bottom}px {padding_left}px"
            else:
                padding_left, padding_top, padding_right, padding_bottom = self._compute_digital_padding()
                padding_rule = "0px"

            self.setStyleSheet(f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    border: {self._bg_border_width}px solid transparent;
                    border-radius: 8px;
                    padding: {padding_rule};
                }}
            """)
            self.setContentsMargins(padding_left, padding_top, padding_right, padding_bottom)
            return

        if self._show_background:
            if self._display_mode == "analog":
                padding_left, padding_top, padding_bottom, _ = self._compute_analog_padding()
                padding_right = padding_left
                padding_rule = f"{padding_top}px {padding_right}px {padding_bottom}px {padding_left}px"
            else:
                padding_left, padding_top, padding_right, padding_bottom = self._compute_digital_padding()
                padding_rule = "0px"

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
                    padding: {padding_rule};
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
                padding_left, padding_top, padding_right, padding_bottom = self._compute_digital_padding()
                self.setStyleSheet(f"""
                    QLabel {{
                        color: rgba({self._text_color.red()}, {self._text_color.green()}, 
                                   {self._text_color.blue()}, {self._text_color.alpha()});
                        background-color: transparent;
                        padding: 0px;
                    }}
                """)
                self.setContentsMargins(padding_left, padding_top, padding_right, padding_bottom)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._display_mode != "analog":
            self._apply_digital_font_fit()
            self._update_stylesheet()
        self._position_timezone_label()
    
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

            shadow_scale = 1.8
            opacity_scale = 3.0

            def _scaled_alpha(base_alpha: int) -> int:
                return min(255, int(round(base_alpha * opacity_scale)))

            metrics = self._compute_analog_layout_metrics()
            if metrics is None:
                return

            center_x = metrics.center_x
            center_y = metrics.center_y
            radius = metrics.radius
            numeral_height = metrics.numeral_height

            numeral_font = QFont(self._font_family, metrics.numeral_pt, QFont.Weight.Black)
            painter.setFont(numeral_font)
            numeral_metrics = painter.fontMetrics()

            if self._show_background:
                self._draw_analog_background_card(painter, center_x, center_y, metrics.card_radius)

            drop_offset = 3
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
                base_alpha = max(121, int(self._text_color.alpha() * 0.605))
                shadow_color = QColor(0, 0, 0, _scaled_alpha(base_alpha))

                ring_path = QPainterPath()
                ring_path.addEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
                ring_stroke = QPainterPathStroker()
                ring_stroke.setWidth(max(4.4, radius * 0.0462))
                ring_stroke.setCapStyle(Qt.PenCapStyle.RoundCap)
                ring_stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                ring_shape = ring_stroke.createStroke(ring_path)

                marker_stroke = QPainterPathStroker()
                marker_stroke.setWidth(max(2.2, radius * 0.01584))
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
            face_pen.setWidth(max(2, int(round(radius * 0.032))))
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
                painter.setFont(numeral_font)
                for hour in range(1, 13):
                    angle = math.radians((hour / 12.0) * 360.0 - 90.0)
                    text = roman_map.get(hour, str(hour))
                    draw_x, baseline_y = self._compute_analog_text_draw_origin(
                        numeral_metrics,
                        text,
                        angle=angle,
                        outer_radius=metrics.numeral_outer_radius,
                        center_x=center_x,
                        center_y=center_y,
                    )

                    if self._analog_face_shadow:
                        base_numeral_alpha = max(175, int(self._text_color.alpha() * 1.0))
                        numeral_shadow = QColor(0, 0, 0, _scaled_alpha(base_numeral_alpha))
                        numeral_offset = max(2, metrics.numeral_shadow_offset_px + 1)
                        painter.setPen(QPen(numeral_shadow))
                        painter.drawText(draw_x + numeral_offset, baseline_y + numeral_offset, text)
                        secondary_shadow = QColor(0, 0, 0, max(0, int(numeral_shadow.alpha() * 0.84)))
                        painter.setPen(QPen(secondary_shadow))
                        painter.drawText(draw_x + 1, baseline_y + 1, text)
                        tertiary_shadow = QColor(0, 0, 0, max(0, int(numeral_shadow.alpha() * 0.58)))
                        painter.setPen(QPen(tertiary_shadow))
                        painter.drawText(draw_x + 2, baseline_y + 1, text)

                    painter.setPen(QPen(self._text_color))
                    painter.drawText(draw_x, baseline_y, text)
        finally:
            painter.end()

        self._cached_clock_face = pixmap
        self._cached_clock_face_size = (width, height)
        self._clock_face_cache_invalidated = False

    def _draw_analog_background_card(
        self,
        painter: QPainter,
        center_x: int,
        center_y: int,
        card_radius: int,
    ) -> None:
        """Paint the analogue clock's circular card + optional outer shadow."""

        card_radius = max(1, int(card_radius))
        card_rect = QRectF(
            float(center_x - card_radius),
            float(center_y - card_radius),
            float(card_radius * 2),
            float(card_radius * 2),
        )

        if self.uses_painted_frame_shadow():
            tuning = PAINTED_FRAME_SHADOW_TUNING
            offset_x = float(tuning["offset_x"])
            offset_y = float(tuning["offset_y"])
            steps = max(1, int(tuning["blur_steps"]))
            spread = max(0.0, float(tuning["spread"]))
            max_alpha = max(0, min(255, int(tuning["max_alpha"])))

            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            for layer in range(steps, 0, -1):
                frac = layer / float(steps)
                grow = spread * frac
                alpha = int(max_alpha * (1.0 - (frac * 0.86)))
                if alpha <= 0:
                    continue
                shadow_rect = card_rect.translated(offset_x, offset_y).adjusted(-grow, -grow, grow, grow)
                painter.setBrush(QColor(0, 0, 0, alpha))
                painter.drawEllipse(shadow_rect)
            painter.restore()

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawEllipse(card_rect)
        if self._bg_border_width > 0 and self._bg_border_color.alpha() > 0:
            border_pen = QPen(self._bg_border_color, max(1, int(self._bg_border_width)))
            border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(card_rect)
        painter.restore()

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

        # Reuse frame buffer to avoid QPixmap allocation every second.
        # Only reallocate when widget size changes.
        dpr = self.devicePixelRatioF()
        fb_size = (int(self.width() * dpr), int(self.height() * dpr))
        if (self._analog_frame_buffer is None or
                self._analog_frame_buffer_size != fb_size):
            self._analog_frame_buffer = QPixmap(fb_size[0], fb_size[1])
            self._analog_frame_buffer.setDevicePixelRatio(dpr)
            self._analog_frame_buffer_size = fb_size
        frame_buffer = self._analog_frame_buffer
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
            shadow_scale = 1.5
            opacity_scale = 2.0

            def _scaled_alpha(base_alpha: int) -> int:
                return min(255, int(round(base_alpha * opacity_scale)))

            metrics = self._compute_analog_layout_metrics()
            if metrics is None:
                fb_painter.end()
                return

            center_x = metrics.center_x
            center_y = metrics.center_y
            radius = metrics.radius
            numeral_height = metrics.numeral_height

            numeral_font = QFont(self._font_family, metrics.numeral_pt, QFont.Weight.Black)
            fb_painter.setFont(numeral_font)

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
            
            # Debug: log second angle periodically
            if self._show_seconds and now.second % 5 == 0 and now.microsecond < 100_000:
                logger.debug(f"[CLOCK_PAINT] sec={sec:.2f}, second_angle={second_angle:.1f}, time={now.strftime('%H:%M:%S')}")

            # Draw hands in order: second, hour, minute so the seconds hand sits below.
            # The seconds hand is drawn without a drop shadow to avoid shadow
            # accumulation artifacts while keeping hour/minute shadows intact.
            if self._show_seconds:
                _draw_hand(second_angle, radius * 0.85, 1, draw_shadow=False)
            _draw_hand(hour_angle, radius * 0.52, max(3, radius // 15), draw_shadow=True)
            _draw_hand(minute_angle, radius * 0.72, max(2, radius // 20), draw_shadow=True)

            # Timezone abbreviation rendered below the analogue clock, centred horizontally.
            if self._show_timezone and self._timezone_abbrev:
                tz_font = QFont(self._font_family, metrics.tz_font_size, QFont.Weight.Bold)
                fb_painter.setFont(tz_font)
                tz_metrics = fb_painter.fontMetrics()
                text = self._timezone_abbrev
                tz_rect = tz_metrics.tightBoundingRect(text)
                if tz_rect.isNull():
                    tz_rect = tz_metrics.boundingRect(text)
                desired_top = self._compute_analog_timezone_top(center_y, radius, numeral_height, metrics)
                tz_x = int(round(center_x - (tz_rect.x() + (tz_rect.width() / 2.0))))
                tz_y = int(round(desired_top - tz_rect.y()))
                fb_painter.setPen(QPen(self._text_color))
                if self._analog_face_shadow:
                    tz_shadow_offset = 3
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

    @dataclass(frozen=True)
    class _AnalogLayoutMetrics:
        center_x: int
        center_y: int
        side: int
        radius: int
        card_radius: int
        numeral_pt: int
        numeral_height: int
        numeral_outer_radius: int
        tz_font_size: int
        numeral_shadow_offset_px: int

    _ANALOG_NUMERAL_PLACEMENTS: dict[str, _AnalogNumeralPlacement] = {
        "I": _AnalogNumeralPlacement(radial_offset_em=0.02),
        "II": _AnalogNumeralPlacement(radial_offset_em=0.02),
        "III": _AnalogNumeralPlacement(radial_offset_em=0.07),
        "IV": _AnalogNumeralPlacement(radial_offset_em=0.05),
        "V": _AnalogNumeralPlacement(radial_offset_em=0.03),
        "VI": _AnalogNumeralPlacement(radial_offset_em=0.05, tangential_offset_em=-0.02),
        "VII": _AnalogNumeralPlacement(radial_offset_em=0.06, tangential_offset_em=-0.03),
        "VIII": _AnalogNumeralPlacement(radial_offset_em=0.18, tangential_offset_em=-0.08),
        "IX": _AnalogNumeralPlacement(radial_offset_em=0.05),
        "X": _AnalogNumeralPlacement(radial_offset_em=0.03),
        "XI": _AnalogNumeralPlacement(radial_offset_em=0.04, tangential_offset_em=0.02),
        "XII": _AnalogNumeralPlacement(radial_offset_em=0.08),
    }

    def _compute_analog_layout_metrics(self) -> Optional["_AnalogLayoutMetrics"]:
        """Return shared analogue geometry metrics for the face, card, and numerals."""
        left_pad, top_pad, bottom_margin, tz_font_size = self._compute_analog_padding()
        if self._show_background:
            rect = self.contentsRect()
        else:
            rect = self.rect().adjusted(left_pad, top_pad, -left_pad, -bottom_margin)

        side = min(rect.width(), rect.height())
        if side <= 0:
            return None

        center_x = rect.x() + rect.width() // 2
        center_y = rect.y() + rect.height() // 2
        card_radius = max(1, side // 2 - 2)

        base_numeral_pt = max(8, min(int(self._font_size * 0.25), max(9, side // 18)))
        numeral_scale = self.ANALOG_FRAMED_NUMERAL_SCALE if self._show_background else self.ANALOG_NUMERAL_SCALE
        numeral_pt = max(7, int(round(base_numeral_pt * numeral_scale)))
        numeral_font = QFont(self._font_family, numeral_pt, QFont.Weight.Black)
        numeral_metrics = QFontMetrics(numeral_font)
        numeral_height = numeral_metrics.height()

        base_ring_width = numeral_height + max(6, numeral_height // 3) - 2
        ring_scale = self.ANALOG_FRAMED_CARD_RING_SCALE if self._show_background else self.ANALOG_CARD_RING_SCALE
        target_ring_width = max(base_ring_width + 2, int(round(base_ring_width * ring_scale)))
        radius = max(12, card_radius - target_ring_width)

        numeral_pull_in = max(2, numeral_height // 3) - 5
        numeral_outer_radius = radius + numeral_height - numeral_pull_in
        numeral_outer_radius = min(card_radius - max(4, numeral_height // 5), numeral_outer_radius)

        base_tz_font_size = tz_font_size
        if self._show_background:
            tz_font_size = max(8, int(round(base_tz_font_size * self.ANALOG_FRAMED_TIMEZONE_SCALE)))
        tz_font_size = min(
            tz_font_size,
            max(8, side // (6 if self._show_background else 5)),
        )

        numeral_shadow_offset_px = 2 if self._show_background else 1

        return self._AnalogLayoutMetrics(
            center_x=center_x,
            center_y=center_y,
            side=side,
            radius=radius,
            card_radius=card_radius,
            numeral_pt=numeral_pt,
            numeral_height=numeral_height,
            numeral_outer_radius=numeral_outer_radius,
            tz_font_size=tz_font_size,
            numeral_shadow_offset_px=numeral_shadow_offset_px,
        )

    def _compute_analog_text_draw_origin(
        self,
        metrics: QFontMetrics,
        text: str,
        *,
        angle: float,
        outer_radius: int,
        center_x: int,
        center_y: int,
    ) -> tuple[int, int]:
        """Return drawText origin using shared radial placement plus optical numeral offsets."""
        rect = metrics.tightBoundingRect(text)
        if rect.isNull():
            rect = metrics.boundingRect(text)

        numeral_height = max(1, rect.height())
        radial_half_extent = (
            abs(math.cos(angle)) * (rect.width() / 2.0)
            + abs(math.sin(angle)) * (rect.height() / 2.0)
        )
        effective_radius = max(0.0, outer_radius - (radial_half_extent * self.ANALOG_NUMERAL_RADIAL_COMPRESS))
        placement = self._ANALOG_NUMERAL_PLACEMENTS.get(text, self._AnalogNumeralPlacement())
        effective_radius += numeral_height * placement.radial_offset_em

        anchor_x = center_x + (math.cos(angle) * effective_radius)
        anchor_y = center_y + (math.sin(angle) * effective_radius)
        tangent_x = -math.sin(angle)
        tangent_y = math.cos(angle)
        tangent_offset = numeral_height * placement.tangential_offset_em
        anchor_x += tangent_x * tangent_offset
        anchor_y += tangent_y * tangent_offset

        draw_x = int(round(anchor_x - (rect.x() + (rect.width() / 2.0))))
        baseline_y = int(round(anchor_y - (rect.y() + (rect.height() / 2.0))))
        return draw_x, baseline_y

    def _compute_analog_timezone_top(
        self,
        center_y: int,
        radius: int,
        numeral_height: int,
        metrics: "_AnalogLayoutMetrics",
    ) -> int:
        """Return desired top edge for analogue timezone text."""
        if self._show_background:
            return center_y + metrics.card_radius + self.ANALOG_FRAMED_TIMEZONE_GAP_PX
        return center_y + radius + numeral_height + self.ANALOG_UNFRAMED_TIMEZONE_GAP_PX

    def _compute_analog_padding(self) -> tuple[int, int, int, int]:
        dpi_y = max(96, int(round(self.logicalDpiY()))) if hasattr(self, "logicalDpiY") else 96
        vertical_padding = max(12, int(round(15 * dpi_y / 96.0)))
        horizontal_padding = vertical_padding
        tz_font_size = max(8, self._font_size // 3)
        widget_height = max(0, int(self.height()))
        if widget_height > 0:
            tz_font_size = min(
                tz_font_size,
                max(8, widget_height // (9 if self._show_background else 8)),
            )
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
        
        metrics = self._compute_analog_layout_metrics()
        if metrics is None:
            return (0, 0)
        
        # If numerals are hidden, the clock face itself is the visual boundary
        if not self._show_numerals:
            visual_top = metrics.center_y - metrics.radius
            visual_left = metrics.center_x - metrics.radius
            return (max(0, visual_left), max(0, visual_top))

        numeral_font = QFont(self._font_family, metrics.numeral_pt, QFont.Weight.Bold)
        numeral_metrics = QFontMetrics(numeral_font)

        xii_x, xii_y = self._compute_analog_text_draw_origin(
            numeral_metrics,
            "XII",
            angle=math.radians(-90.0),
            outer_radius=metrics.numeral_outer_radius,
            center_x=metrics.center_x,
            center_y=metrics.center_y,
        )
        ix_x, ix_y = self._compute_analog_text_draw_origin(
            numeral_metrics,
            "IX",
            angle=math.radians(180.0),
            outer_radius=metrics.numeral_outer_radius,
            center_x=metrics.center_x,
            center_y=metrics.center_y,
        )
        xii_rect = numeral_metrics.tightBoundingRect("XII")
        if xii_rect.isNull():
            xii_rect = numeral_metrics.boundingRect("XII")
        ix_rect = numeral_metrics.tightBoundingRect("IX")
        if ix_rect.isNull():
            ix_rect = numeral_metrics.boundingRect("IX")

        visual_top = xii_y + xii_rect.y()
        visual_left = ix_x + ix_rect.x()
        
        return (max(0, visual_left), max(0, visual_top))
    
    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up clock widget")
        self.stop()
        if self._tz_label:
            self._tz_label.deleteLater()
            self._tz_label = None
