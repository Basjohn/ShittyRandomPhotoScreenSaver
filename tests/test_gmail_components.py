"""Tests for Gmail components (GmailPosition enum, formatting utilities)."""
from __future__ import annotations


def test_gmail_position_enum_values() -> None:
    """Verify GmailPosition enum has all standard overlay position values."""
    from widgets.gmail_components import GmailPosition

    assert [pos.value for pos in GmailPosition] == [
        "top_left",
        "top_center",
        "top_right",
        "middle_left",
        "center",
        "middle_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    ]


def test_gmail_position_from_string() -> None:
    """Verify GmailPosition.from_string() recognizes UI and persisted positions."""
    from widgets.gmail_components import GmailPosition

    assert GmailPosition.from_string("top_left") == GmailPosition.TOP_LEFT
    assert GmailPosition.from_string("Top Center") == GmailPosition.TOP_CENTER
    assert GmailPosition.from_string("top_right") == GmailPosition.TOP_RIGHT
    assert GmailPosition.from_string("Middle Left") == GmailPosition.MIDDLE_LEFT
    assert GmailPosition.from_string("center") == GmailPosition.CENTER
    assert GmailPosition.from_string("Middle Right") == GmailPosition.MIDDLE_RIGHT
    assert GmailPosition.from_string("bottom_left") == GmailPosition.BOTTOM_LEFT
    assert GmailPosition.from_string("Bottom Center") == GmailPosition.BOTTOM_CENTER
    assert GmailPosition.from_string("bottom_right") == GmailPosition.BOTTOM_RIGHT
    assert GmailPosition.from_string("Custom") == GmailPosition.TOP_LEFT

    # Test that unknown positions default to TOP_LEFT
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

    assert GmailPosition.TOP_LEFT.value == "top_left"
    assert GmailPosition.TOP_CENTER.value == "top_center"
    assert GmailPosition.TOP_RIGHT.value == "top_right"
    assert GmailPosition.MIDDLE_LEFT.value == "middle_left"
    assert GmailPosition.CENTER.value == "center"
    assert GmailPosition.MIDDLE_RIGHT.value == "middle_right"
    assert GmailPosition.BOTTOM_LEFT.value == "bottom_left"
    assert GmailPosition.BOTTOM_CENTER.value == "bottom_center"
    assert GmailPosition.BOTTOM_RIGHT.value == "bottom_right"


def test_smart_title_case() -> None:
    """Verify _smart_title_case() function capitalizes words correctly."""
    from widgets.gmail_components import _smart_title_case, smart_title_case_subject

    assert _smart_title_case("hello world") == "Hello World"
    assert _smart_title_case("") == ""
    assert _smart_title_case("test") == "Test"
    assert _smart_title_case("multiple words here") == "Multiple Words Here"
    assert _smart_title_case("you've been invited") == "You've Been Invited"
    assert smart_title_case_subject("you'll need 2FA for AI") == "You'll Need 2FA For AI"
    # Preserves ALL CAPS (acronyms)
    assert _smart_title_case("GMAIL") == "GMAIL"
    assert _smart_title_case("NASA") == "NASA"


def test_gmail_sender_cleanup() -> None:
    """Verify noisy sender headers are reduced to useful display names."""
    from widgets.gmail_components import clean_sender_name, title_case_sender_name

    assert clean_sender_name("PayPal <service@paypal.com>") == "PayPal"
    assert clean_sender_name('"Battle.net" <noreply@battle.net>') == "Battle.net"
    assert clean_sender_name("takealot.com <info@takealot.com>") == "Takealot.com"
    assert clean_sender_name("Rene van Heerden via alerts") == "Rene van Heerden"
    assert clean_sender_name("alerts@talkwalker.com") == "Talkwalker"
    assert clean_sender_name("FNB - Investment Alerts") == "FNB"
    assert clean_sender_name("AI <alerts@example.com>") == "AI"
    assert clean_sender_name("One Two Three Four", max_words=3) == "One Two Three..."
    assert clean_sender_name("PayPal <service@paypal.com>", enabled=False) == "PayPal <service@paypal.com>"
    assert title_case_sender_name("alerts@talkwalker.com") == "Alerts@talkwalker.com"
    assert title_case_sender_name("takealot.com") == "Takealot.com"
    assert title_case_sender_name("ChatGPT") == "ChatGPT"


def test_gmail_subject_shortening() -> None:
    """Verify subject word/character limits follow Gmail display rules."""
    from widgets.gmail_components import shorten_subject

    assert shorten_subject("Receipt For Your Payment To COGNOSPHERE", max_words=4) == "Receipt For Your Payment..."
    assert shorten_subject("Receipt For Your Payment To COGNOSPHERE", max_words=0, max_chars=20) == "Receipt For Your Pay..."
    assert shorten_subject("One two three four five", max_words=4, max_chars=25) == "One two three four five"
    assert shorten_subject("Receipt For Your Payment To COGNOSPHERE", max_words=4, max_chars=20) == "Receipt For Your Pay..."
    assert shorten_subject("One two three four", max_words=0, max_chars=0) == "One two three four"
    assert shorten_subject("PayPal | Receipt For Your Payment", max_words=4) == "PayPal | Receipt For Your..."
    assert shorten_subject("Takealot - Payment Confirmation", max_words=2) == "Takealot - Payment..."


def test_format_relative_time() -> None:
    """Verify _format_relative_time() returns human-readable time strings."""
    from datetime import datetime, timedelta
    from widgets.gmail_components import _format_relative_time

    now = datetime(2026, 4, 29, 12, 0, 0)

    # Test various time differences
    assert _format_relative_time(now - timedelta(minutes=1), now=now) == "1 min ago"
    assert _format_relative_time(now - timedelta(hours=1), now=now) == "1 hr ago"
    assert _format_relative_time(now - timedelta(days=1), now=now) == "Yesterday"
    assert _format_relative_time(now - timedelta(days=7), now=now) == "Last Week"
    assert _format_relative_time(now - timedelta(days=40), now=now) == "Last Month"
    assert _format_relative_time(now - timedelta(days=800), now=now) == "Two Years Ago"

    # Test future time (edge case)
    future = now + timedelta(minutes=5)
    result = _format_relative_time(future, now=now)
    assert result == ""  # Future times return empty string


def test_format_email_date_modes() -> None:
    """Verify Gmail date display modes."""
    from datetime import datetime, timedelta
    from widgets.gmail_components import format_email_date

    now = datetime(2026, 4, 29, 12, 0, 0)
    date = datetime(2026, 4, 16, 9, 30, 0)
    old_date = datetime(2025, 6, 23, 9, 30, 0)

    assert format_email_date(now - timedelta(days=1), "relative", now=now) == "Yesterday"
    assert format_email_date(date, "numeric", now=now) == "16/04"
    assert format_email_date(old_date, "numeric", now=now) == "23/06/2025"
    assert format_email_date(date, "words", now=now) == "April 16th"
    assert format_email_date(old_date, "words", now=now) == "June 23rd 2025"
