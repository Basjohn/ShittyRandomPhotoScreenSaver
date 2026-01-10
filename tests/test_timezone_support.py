"""
Tests for timezone support in clock widget.

Tests timezone parsing, auto-detection, and display functionality.
"""
import pytest
from datetime import timezone, timedelta
from PySide6.QtWidgets import QWidget

from widgets.clock_widget import ClockWidget, TimeFormat, PYTZ_AVAILABLE
from widgets.timezone_utils import (
    get_local_timezone, get_common_timezones,  
    get_all_pytz_timezones, validate_timezone
)


class TestTimezoneUtils:
    """Test timezone utility functions."""
    
    def test_get_local_timezone(self):
        """Test local timezone detection."""
        tz = get_local_timezone()
        assert tz is not None
        assert isinstance(tz, str)
        # Should return either 'local', a pytz timezone name, or UTC offset
        assert tz == 'local' or tz.startswith('UTC') or '/' in tz
    
    def test_get_common_timezones(self):
        """Test common timezones list."""
        timezones = get_common_timezones()
        assert len(timezones) > 0
        
        # Check structure
        for display_name, tz_str in timezones:
            assert isinstance(display_name, str)
            assert isinstance(tz_str, str)
        
        # Check that 'Local Time' and 'UTC' are included
        tz_strs = [tz[1] for tz in timezones]
        assert 'local' in tz_strs
        assert 'UTC' in tz_strs
        
        # Check some major cities (if pytz available)
        if PYTZ_AVAILABLE:
            assert 'US/Eastern' in tz_strs
            assert 'Europe/London' in tz_strs
            assert 'Asia/Tokyo' in tz_strs
    
    def test_get_all_pytz_timezones(self):
        """Test full pytz timezone list."""
        if not PYTZ_AVAILABLE:
            timezones = get_all_pytz_timezones()
            assert len(timezones) == 0
            return
        
        timezones = get_all_pytz_timezones()
        assert len(timezones) > 100  # Should have many timezones
        
        # Check structure
        for display_name, tz_str in timezones:
            assert isinstance(display_name, str)
            assert isinstance(tz_str, str)
    
    def test_validate_timezone_local(self):
        """Test validation of 'local' timezone."""
        assert validate_timezone('local') == True
        assert validate_timezone('') == True
    
    def test_validate_timezone_utc_offsets(self):
        """Test validation of UTC offset strings."""
        # Valid offsets
        assert validate_timezone('UTC') == True
        assert validate_timezone('UTC+0') == True
        assert validate_timezone('UTC-0') == True
        assert validate_timezone('UTC+5') == True
        assert validate_timezone('UTC-7') == True
        assert validate_timezone('UTC+5:30') == True
        assert validate_timezone('UTC-3:45') == True
        assert validate_timezone('UTC+12') == True
        assert validate_timezone('UTC-12') == True
        
        # Invalid offsets
        assert validate_timezone('UTC+25') == False  # Out of range
        assert validate_timezone('UTC-15') == False  # Out of range
        assert validate_timezone('UTC+5:70') == False  # Invalid minutes
        assert validate_timezone('UTC+abc') == False  # Invalid format
    
    @pytest.mark.skipif(not PYTZ_AVAILABLE, reason="pytz not installed")
    def test_validate_timezone_pytz(self):
        """Test validation of pytz timezone names."""
        assert validate_timezone('US/Eastern') == True
        assert validate_timezone('Europe/London') == True
        assert validate_timezone('Asia/Tokyo') == True
        assert validate_timezone('Australia/Sydney') == True
        
        # Invalid timezone
        assert validate_timezone('Invalid/Timezone') == False


class TestClockWidgetTimezone:
    """Test ClockWidget timezone functionality."""
    
    def test_clock_creation_default_timezone(self, qt_app):
        """Test clock widget creation with default (local) timezone."""
        parent = QWidget()
        clock = ClockWidget(parent)
        
        assert clock._timezone_str == 'local'
        assert clock._timezone is None  # None means local time
        assert clock._show_timezone == False
    
    def test_clock_creation_with_timezone(self, qt_app):
        """Test clock widget creation with specific timezone."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC', show_timezone=True)
        
        assert clock._timezone_str == 'UTC'
        assert clock._timezone is not None
        assert clock._show_timezone == True
    
    def test_clock_parse_utc_offset_positive(self, qt_app):
        """Test parsing positive UTC offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC+5')
        
        assert clock._timezone is not None
        assert isinstance(clock._timezone, timezone)
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=5)
    
    def test_clock_parse_utc_offset_negative(self, qt_app):
        """Test parsing negative UTC offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC-7')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=-7)
    
    def test_clock_parse_utc_offset_with_minutes(self, qt_app):
        """Test parsing UTC offset with minutes."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC+5:30')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=5, minutes=30)
    
    @pytest.mark.skipif(not PYTZ_AVAILABLE, reason="pytz not installed")
    def test_clock_parse_pytz_timezone(self, qt_app):
        """Test parsing pytz timezone name."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='US/Eastern')
        
        assert clock._timezone is not None
        assert hasattr(clock._timezone, 'zone')
        assert clock._timezone.zone == 'US/Eastern'
    
    def test_clock_timezone_abbrev_local(self, qt_app):
        """Test timezone abbreviation for local time."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='local')
        
        abbrev = clock._get_timezone_abbrev()
        assert abbrev is not None
        assert isinstance(abbrev, str)
        assert len(abbrev) > 0  # Should have some abbreviation
    
    def test_clock_timezone_abbrev_utc(self, qt_app):
        """Test timezone abbreviation for UTC."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC')
        
        abbrev = clock._get_timezone_abbrev()
        assert abbrev == 'UTC'
    
    def test_clock_timezone_abbrev_offset(self, qt_app):
        """Test timezone abbreviation for UTC offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC+5:30')
        
        abbrev = clock._get_timezone_abbrev()
        assert abbrev == 'UTC+5:30'
    
    def test_clock_set_timezone(self, qt_app):
        """Test dynamically changing timezone."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='local')
        
        # Change to UTC+3
        clock.set_timezone('UTC+3')
        assert clock._timezone_str == 'UTC+3'
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=3)
    
    def test_clock_set_show_timezone(self, qt_app):
        """Test toggling timezone abbreviation display."""
        parent = QWidget()
        clock = ClockWidget(parent, show_timezone=False)
        
        assert clock._show_timezone == False
        
        clock.set_show_timezone(True)
        assert clock._show_timezone == True
    
    def test_clock_time_update_with_timezone(self, qt_app):
        """Test that time updates work with timezone set."""
        parent = QWidget()
        parent.resize(800, 600)
        clock = ClockWidget(parent, timezone_str='UTC', show_timezone=True)
        clock.start()
        
        # Process events to ensure update happens
        qt_app.processEvents()
        
        # Check that text is set
        text = clock.text()
        assert len(text) > 0
        # Should include 'UTC' abbreviation
        assert 'UTC' in text or 'GMT' in text
        
        clock.stop()
    
    def test_clock_local_vs_utc_time_difference(self, qt_app):
        """Test that UTC clock shows different time than local (usually)."""
        parent = QWidget()
        parent.resize(800, 600)
        
        local_clock = ClockWidget(parent, timezone_str='local',
                                 time_format=TimeFormat.TWENTY_FOUR_HOUR,
                                 show_seconds=True)
        utc_clock = ClockWidget(parent, timezone_str='UTC',
                               time_format=TimeFormat.TWENTY_FOUR_HOUR,
                               show_seconds=True)
        
        local_clock.start()
        utc_clock.start()
        
        qt_app.processEvents()
        
        local_text = local_clock.text()
        utc_text = utc_clock.text()
        
        # Both should have text
        assert len(local_text) > 0
        assert len(utc_text) > 0
        
        # In most timezones, they will be different
        # (unless you're in UTC timezone, in which case they'll match)
        # We can't assert they're different because tests might run in UTC
        
        local_clock.stop()
        utc_clock.stop()
    
    def test_clock_invalid_timezone_fallback(self, qt_app):
        """Test that invalid timezone falls back to local."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='Invalid/Timezone')
        
        # Should fall back to None (local time)
        assert clock._timezone is None
    
    def test_clock_timezone_display_formats(self, qt_app):
        """Test timezone with different time formats."""
        parent = QWidget()
        parent.resize(800, 600)
        
        # 12-hour format with timezone
        clock_12h = ClockWidget(parent, time_format=TimeFormat.TWELVE_HOUR,
                                timezone_str='UTC', show_timezone=True)
        clock_12h.start()
        qt_app.processEvents()
        text_12h = clock_12h.text()
        assert 'AM' in text_12h or 'PM' in text_12h
        assert 'UTC' in text_12h or 'GMT' in text_12h
        clock_12h.stop()
        
        # 24-hour format with timezone
        clock_24h = ClockWidget(parent, time_format=TimeFormat.TWENTY_FOUR_HOUR,
                                timezone_str='UTC', show_timezone=True)
        clock_24h.start()
        qt_app.processEvents()
        text_24h = clock_24h.text()
        assert 'AM' not in text_24h and 'PM' not in text_24h
        assert 'UTC' in text_24h or 'GMT' in text_24h
        clock_24h.stop()


class TestTimezoneEdgeCases:
    """Test edge cases and unusual timezone scenarios."""
    
    def test_timezone_negative_half_hour(self, qt_app):
        """Test negative half-hour offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC-3:30')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=-3, minutes=-30)
    
    def test_timezone_45_minute_offset(self, qt_app):
        """Test 45-minute offset (e.g., Nepal UTC+5:45)."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC+5:45')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=5, minutes=45)
    
    def test_timezone_extreme_positive(self, qt_app):
        """Test extreme positive offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC+14')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=14)
    
    def test_timezone_extreme_negative(self, qt_app):
        """Test extreme negative offset."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='UTC-12')
        
        assert clock._timezone is not None
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(hours=-12)
    
    def test_empty_timezone_string(self, qt_app):
        """Test empty timezone string."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='')
        
        # Should default to local
        assert clock._timezone is None
    
    def test_case_insensitive_utc(self, qt_app):
        """Test that 'utc' (lowercase) works."""
        parent = QWidget()
        clock = ClockWidget(parent, timezone_str='utc')
        
        assert clock._timezone is not None
        # Should be recognized as UTC
        offset = clock._timezone.utcoffset(None)
        assert offset == timedelta(0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
