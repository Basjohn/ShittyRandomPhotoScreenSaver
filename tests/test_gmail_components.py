"""Tests for Gmail components (GmailPosition enum, formatting utilities)."""
from __future__ import annotations


def test_gmail_position_enum_values() -> None:
    """Verify GmailPosition enum has all four corner position values."""
    from widgets.gmail_components import GmailPosition

    # Check all four corner positions exist
    assert GmailPosition.TOP_LEFT is not None
    assert GmailPosition.TOP_RIGHT is not None
    assert GmailPosition.BOTTOM_LEFT is not None
    assert GmailPosition.BOTTOM_RIGHT is not None


def test_gmail_position_from_string() -> None:
    """Verify GmailPosition.from_string() recognizes corner positions."""
    from widgets.gmail_components import GmailPosition

    # Test standard snake_case values for corner positions
    assert GmailPosition.from_string("top_left") == GmailPosition.TOP_LEFT
    assert GmailPosition.from_string("top_right") == GmailPosition.TOP_RIGHT
    assert GmailPosition.from_string("bottom_left") == GmailPosition.BOTTOM_LEFT
    assert GmailPosition.from_string("bottom_right") == GmailPosition.BOTTOM_RIGHT

    # Test that unknown positions default to TOP_LEFT
    assert GmailPosition.from_string("center") == GmailPosition.TOP_LEFT
    assert GmailPosition.from_string("invalid") == GmailPosition.TOP_LEFT


def test_gmail_position_from_string_invalid() -> None:
    """Verify GmailPosition.from_string() defaults to TOP_LEFT for invalid strings."""
    from widgets.gmail_components import GmailPosition

    # Invalid strings should default to TOP_LEFT (not raise ValueError)
    assert GmailPosition.from_string("invalid_position") == GmailPosition.TOP_LEFT
    assert GmailPosition.from_string("") == GmailPosition.TOP_LEFT


def test_gmail_position_value_property() -> None:
    """Verify GmailPosition.value returns correct position strings."""
    from widgets.gmail_components import GmailPosition

    # Values are lowercase snake_case
    assert GmailPosition.TOP_LEFT.value == "top_left"
    assert GmailPosition.TOP_RIGHT.value == "top_right"
    assert GmailPosition.BOTTOM_LEFT.value == "bottom_left"
    assert GmailPosition.BOTTOM_RIGHT.value == "bottom_right"


def test_smart_title_case() -> None:
    """Verify _smart_title_case() function capitalizes words correctly."""
    from widgets.gmail_components import _smart_title_case

    assert _smart_title_case("hello world") == "Hello World"
    assert _smart_title_case("") == ""
    assert _smart_title_case("test") == "Test"
    assert _smart_title_case("multiple words here") == "Multiple Words Here"
    # Preserves ALL CAPS (acronyms)
    assert _smart_title_case("GMAIL") == "GMAIL"
    assert _smart_title_case("NASA") == "NASA"


def test_format_relative_time() -> None:
    """Verify _format_relative_time() returns human-readable time strings."""
    from datetime import datetime, timedelta
    from widgets.gmail_components import _format_relative_time

    now = datetime.now()

    # Test various time differences
    assert _format_relative_time(now - timedelta(minutes=1)) in ["1 min ago"]
    assert _format_relative_time(now - timedelta(hours=1)) in ["1 hr ago"]
    assert _format_relative_time(now - timedelta(days=1)) in ["Yesterday"]
    # For 7+ days, it returns "Mon" (weekday) for < 7 days, "Apr 20" (month day) for >= 7 days
    result_7days = _format_relative_time(now - timedelta(days=7))
    assert result_7days in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] or len(result_7days) >= 3

    # Test future time (edge case)
    future = now + timedelta(minutes=5)
    result = _format_relative_time(future)
    assert result == ""  # Future times return empty string
