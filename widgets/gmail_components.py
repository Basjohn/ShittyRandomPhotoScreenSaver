"""Gmail widget helper components.

Extracted from gmail_widget.py to keep the main widget under the 1500-line
monolith threshold. Contains:
- GmailPosition — enum for widget screen position
- _format_relative_time — lightweight datetime formatting
- _smart_title_case — title casing utility (reuses Reddit logic)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import json
import re
from typing import Any, List, Optional

from core.logging.logger import get_logger
from core.gmail.gmail_client import EmailMetadata

logger = get_logger(__name__)


class GmailPosition(Enum):
    """Gmail widget position on screen (corner positions)."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"

    @classmethod
    def from_string(cls, value: str) -> "GmailPosition":
        """Convert string to GmailPosition, with fallback to TOP_LEFT."""
        try:
            return cls(value.lower().replace(" ", "_"))
        except ValueError:
            logger.warning("[GMAIL] Unknown position '%s', defaulting to TOP_LEFT", value)
            return cls.TOP_LEFT


_TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)


def _format_relative_time(dt: datetime) -> str:
    """Format a datetime as a human-readable relative string.

    Examples: "2 min ago", "1 hr ago", "Yesterday", "Mon 14:32".
    No external dependencies — uses datetime arithmetic only.
    """
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    delta = now - dt

    if delta < timedelta(seconds=0):
        return ""
    if delta < timedelta(minutes=1):
        return "Just now"
    if delta < timedelta(hours=1):
        mins = int(delta.total_seconds() // 60)
        return f"{mins} min ago"
    if delta < timedelta(hours=24):
        hrs = int(delta.total_seconds() // 3600)
        return f"{hrs} hr ago"
    if delta < timedelta(days=2):
        return "Yesterday"
    if delta < timedelta(days=7):
        return dt.strftime("%a")
    return dt.strftime("%b %d")


def _smart_title_case(text: str) -> str:
    """Convert text to title case while preserving acronyms and handling exceptions.

    - Preserves ALL CAPS words (likely acronyms: USA, NASA, AI, etc.)
    - Capitalizes every word (including short words like "a", "to", "with")
    - Preserves standalone "I"
    - Handles punctuation correctly
    """
    if not text:
        return text

    # Split by non-word characters (preserving them)
    words = re.split(r"([^\w])", text)

    result = []
    for word in words:
        if not word:
            continue
        # Preserve non-word characters
        if not word.isalnum():
            result.append(word)
            continue
        # Preserve ALL CAPS (acronyms)
        if word.isupper() and len(word) > 1:
            result.append(word)
            continue
        # Preserve standalone "I"
        if word == "i" or word == "I":
            result.append("I")
            continue
        result.append(word.capitalize())

    return "".join(result)


def _email_to_cache_dict(email: EmailMetadata) -> dict[str, Any]:
    """Serialize EmailMetadata to a JSON-safe dict (no sensitive data)."""
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "subject": email.subject,
        "date_iso": email.date.isoformat() if email.date else None,
        "labels": list(email.labels),
        "is_unread": email.is_unread,
    }


def _email_from_cache_dict(data: dict[str, Any]) -> Optional[EmailMetadata]:
    """Deserialize a dict back to EmailMetadata."""
    try:
        date_str = data.get("date_iso")
        date = datetime.fromisoformat(date_str) if date_str else None
        labels = tuple(data.get("labels", []))
        return EmailMetadata(
            id=data["id"],
            thread_id=data["thread_id"],
            sender=data["sender"],
            subject=data["subject"],
            date=date,
            labels=labels,
            is_unread=data["is_unread"],
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("[GMAIL] Failed to deserialize cached email: %s", e)
        return None


def serialize_email_cache(emails: List[EmailMetadata]) -> str:
    """Serialize a list of EmailMetadata to a JSON string."""
    return json.dumps([_email_to_cache_dict(e) for e in emails], indent=2)


def deserialize_email_cache(data: str) -> List[EmailMetadata]:
    """Deserialize a JSON string back to a list of EmailMetadata."""
    try:
        items = json.loads(data)
        if not isinstance(items, list):
            return []
        return [e for e in (_email_from_cache_dict(item) for item in items) if e is not None]
    except json.JSONDecodeError as e:
        logger.warning("[GMAIL] Failed to deserialize email cache: %s", e)
        return []
