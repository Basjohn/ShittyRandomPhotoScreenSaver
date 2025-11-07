"""
Timezone utilities for clock widget.

Provides timezone detection, common timezone lists, and helper functions.
"""
from typing import List, Tuple
import time
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

from core.logging.logger import get_logger

logger = get_logger(__name__)


def get_local_timezone() -> str:
    """
    Auto-detect user's local timezone.
    
    Returns:
        Timezone string ('local' if detection fails, pytz timezone name if successful)
    """
    if not PYTZ_AVAILABLE:
        return 'local'
    
    try:
        # Get system timezone offset
        if time.daylight:
            offset = -time.altzone
        else:
            offset = -time.timezone
        
        # Get timezone name
        tz_name = time.tzname[time.daylight]
        
        # Try to match with pytz timezone
        # First, try common_timezones matching the abbreviation
        for tz in pytz.common_timezones:
            try:
                tz_obj = pytz.timezone(tz)
                # Check if offset matches at current time
                from datetime import datetime
                now = datetime.now(tz_obj)
                if now.utcoffset().total_seconds() == offset:
                    logger.info(f"Auto-detected timezone: {tz}")
                    return tz
            except Exception:
                continue
        
        # Fallback: return UTC offset
        hours = int(offset / 3600)
        minutes = abs(int((offset % 3600) / 60))
        if minutes == 0:
            return f"UTC{hours:+d}"
        else:
            return f"UTC{hours:+d}:{minutes:02d}"
        
    except Exception as e:
        logger.warning(f"Failed to auto-detect timezone: {e}")
        return 'local'


def get_common_timezones() -> List[Tuple[str, str]]:
    """
    Get list of common timezones with display names.
    
    Returns:
        List of (display_name, timezone_str) tuples
    """
    timezones = [
        ("Local Time", "local"),
        ("UTC", "UTC"),
    ]
    
    if PYTZ_AVAILABLE:
        # Add major world cities and regions
        common_zones = [
            ("US/Eastern", "US/Eastern"),
            ("US/Central", "US/Central"),
            ("US/Mountain", "US/Mountain"),
            ("US/Pacific", "US/Pacific"),
            ("US/Alaska", "US/Alaska"),
            ("US/Hawaii", "US/Hawaii"),
            ("Canada/Eastern", "Canada/Eastern"),
            ("Canada/Central", "Canada/Central"),
            ("Canada/Mountain", "Canada/Mountain"),
            ("Canada/Pacific", "Canada/Pacific"),
            ("Europe/London", "Europe/London"),
            ("Europe/Paris", "Europe/Paris"),
            ("Europe/Berlin", "Europe/Berlin"),
            ("Europe/Rome", "Europe/Rome"),
            ("Europe/Madrid", "Europe/Madrid"),
            ("Europe/Moscow", "Europe/Moscow"),
            ("Asia/Tokyo", "Asia/Tokyo"),
            ("Asia/Shanghai", "Asia/Shanghai"),
            ("Asia/Hong_Kong", "Asia/Hong_Kong"),
            ("Asia/Singapore", "Asia/Singapore"),
            ("Asia/Dubai", "Asia/Dubai"),
            ("Asia/Kolkata", "Asia/Kolkata"),
            ("Asia/Bangkok", "Asia/Bangkok"),
            ("Asia/Seoul", "Asia/Seoul"),
            ("Australia/Sydney", "Australia/Sydney"),
            ("Australia/Melbourne", "Australia/Melbourne"),
            ("Australia/Perth", "Australia/Perth"),
            ("Pacific/Auckland", "Pacific/Auckland"),
            ("America/New_York", "America/New_York"),
            ("America/Chicago", "America/Chicago"),
            ("America/Denver", "America/Denver"),
            ("America/Los_Angeles", "America/Los_Angeles"),
            ("America/Mexico_City", "America/Mexico_City"),
            ("America/Sao_Paulo", "America/Sao_Paulo"),
            ("America/Buenos_Aires", "America/Buenos_Aires"),
            ("Africa/Cairo", "Africa/Cairo"),
            ("Africa/Johannesburg", "Africa/Johannesburg"),
            ("Africa/Lagos", "Africa/Lagos"),
        ]
        
        timezones.extend(common_zones)
    
    # Add custom UTC offsets
    utc_offsets = [
        ("UTC-12:00", "UTC-12"),
        ("UTC-11:00", "UTC-11"),
        ("UTC-10:00", "UTC-10"),
        ("UTC-9:00", "UTC-9"),
        ("UTC-8:00", "UTC-8"),
        ("UTC-7:00", "UTC-7"),
        ("UTC-6:00", "UTC-6"),
        ("UTC-5:00", "UTC-5"),
        ("UTC-4:00", "UTC-4"),
        ("UTC-3:00", "UTC-3"),
        ("UTC-2:00", "UTC-2"),
        ("UTC-1:00", "UTC-1"),
        ("UTC+0:00", "UTC+0"),
        ("UTC+1:00", "UTC+1"),
        ("UTC+2:00", "UTC+2"),
        ("UTC+3:00", "UTC+3"),
        ("UTC+3:30", "UTC+3:30"),
        ("UTC+4:00", "UTC+4"),
        ("UTC+4:30", "UTC+4:30"),
        ("UTC+5:00", "UTC+5"),
        ("UTC+5:30", "UTC+5:30"),
        ("UTC+5:45", "UTC+5:45"),
        ("UTC+6:00", "UTC+6"),
        ("UTC+6:30", "UTC+6:30"),
        ("UTC+7:00", "UTC+7"),
        ("UTC+8:00", "UTC+8"),
        ("UTC+8:45", "UTC+8:45"),
        ("UTC+9:00", "UTC+9"),
        ("UTC+9:30", "UTC+9:30"),
        ("UTC+10:00", "UTC+10"),
        ("UTC+10:30", "UTC+10:30"),
        ("UTC+11:00", "UTC+11"),
        ("UTC+12:00", "UTC+12"),
        ("UTC+12:45", "UTC+12:45"),
        ("UTC+13:00", "UTC+13"),
        ("UTC+14:00", "UTC+14"),
    ]
    
    timezones.extend(utc_offsets)
    
    return timezones


def get_all_pytz_timezones() -> List[Tuple[str, str]]:
    """
    Get all available pytz timezones.
    
    Returns:
        List of (display_name, timezone_str) tuples, or empty list if pytz not available
    """
    if not PYTZ_AVAILABLE:
        return []
    
    timezones = []
    for tz in sorted(pytz.all_timezones):
        # Format display name (replace underscores with spaces)
        display_name = tz.replace('_', ' ')
        timezones.append((display_name, tz))
    
    return timezones


def validate_timezone(timezone_str: str) -> bool:
    """
    Validate timezone string.
    
    Args:
        timezone_str: Timezone string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if timezone_str == 'local' or not timezone_str:
        return True
    
    # Check pytz timezone
    if PYTZ_AVAILABLE:
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.UnknownTimeZoneError:
            pass
    
    # Check UTC offset format
    if timezone_str.upper().startswith('UTC'):
        try:
            offset_str = timezone_str[3:]
            if not offset_str or offset_str in ('+0', '-0', '+0:00', '-0:00'):
                return True
            
            if offset_str[0] in ('+', '-'):
                offset_str = offset_str[1:]
            
            # Parse hours and minutes
            if ':' in offset_str:
                hours_str, minutes_str = offset_str.split(':')
                hours = int(hours_str)
                minutes = int(minutes_str)
                # Validate range
                if -12 <= hours <= 14 and 0 <= minutes < 60:
                    return True
            else:
                hours = int(offset_str)
                if -12 <= hours <= 14:
                    return True
        except (ValueError, IndexError):
            pass
    
    return False
