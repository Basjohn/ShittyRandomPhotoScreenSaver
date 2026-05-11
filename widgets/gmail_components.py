"""Gmail widget helper components.

Extracted from gmail_widget.py to keep the main widget under the 1500-line
monolith threshold. Contains:
- GmailPosition — enum for widget screen position
- _format_relative_time — lightweight datetime formatting
- _smart_title_case — title casing utility (reuses Reddit logic)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr
from enum import Enum
import json
import re
import unicodedata
from typing import Any, List, Optional

from core.logging.logger import get_logger
from core.gmail.gmail_client import EmailMetadata

logger = get_logger(__name__)


class GmailPosition(Enum):
    """Gmail widget position on screen."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"

    @classmethod
    def from_string(cls, value: str) -> "GmailPosition":
        """Convert string to GmailPosition, with fallback to TOP_LEFT."""
        if not value:
            logger.warning("[GMAIL] Unknown position '%s', defaulting to TOP_LEFT", value)
            return cls.TOP_LEFT
        normalized = value.lower().replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            logger.warning("[GMAIL] Unknown position '%s', defaulting to TOP_LEFT", value)
            return cls.TOP_LEFT


_TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)
_TITLE_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")
_SENDER_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_NOISY_LOCAL_PARTS = {"no-reply", "noreply", "notification", "notifications", "alert", "alerts"}


def _number_word(value: int) -> str:
    words = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
        9: "Nine",
        10: "Ten",
    }
    return words.get(value, str(value))


def _ordinal_suffix(day: int) -> str:
    if 10 <= day % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _format_words_date(dt: datetime, now: Optional[datetime] = None) -> str:
    current = now or (datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now())
    text = f"{dt.strftime('%B')} {dt.day}{_ordinal_suffix(dt.day)}"
    if dt.year != current.year:
        text = f"{text} {dt.year}"
    return text


def _format_numeric_date(dt: datetime, now: Optional[datetime] = None) -> str:
    current = now or (datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now())
    if dt.year == current.year:
        return dt.strftime("%d/%m")
    return dt.strftime("%d/%m/%Y")


def _format_relative_time(dt: datetime, now: Optional[datetime] = None) -> str:
    """Format a datetime as a human-readable relative string.

    Examples: "2 min ago", "1 hr ago", "Yesterday", "Mon 14:32".
    No external dependencies — uses datetime arithmetic only.
    """
    now = now or (datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now())
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
    if delta < timedelta(days=14):
        return "Last Week"
    if delta < timedelta(days=60):
        return "Last Month"
    if delta < timedelta(days=365):
        months = max(2, int(delta.days // 30))
        return f"{_number_word(months)} Months Ago"
    if delta < timedelta(days=730):
        return "Last Year"
    years = max(2, int(delta.days // 365))
    return f"{_number_word(years)} Years Ago"


def format_email_date(dt: datetime, mode: str = "relative", now: Optional[datetime] = None) -> str:
    """Format an email date for Gmail row display."""
    normalized = str(mode or "relative").strip().lower()
    if normalized == "numeric":
        return _format_numeric_date(dt, now)
    if normalized == "words":
        return _format_words_date(dt, now)
    return _format_relative_time(dt, now)


def _decode_mime_header(raw: str) -> str:
    """Decode a MIME-encoded header value, falling back to the raw text."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(str(raw))))
    except Exception:
        return str(raw)


def _clean_spaces(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "")).strip()


def _trim_ellipsis_source(text: str) -> str:
    return text.rstrip(" \t\r\n.,;:-")


def _append_ellipsis(text: str, shortened: bool) -> str:
    if not shortened:
        return text
    body = _trim_ellipsis_source(text)
    return f"{body}..." if body else "..."


def _coerce_limit(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _limit_words(text: str, max_words: int) -> tuple[str, bool]:
    max_words = _coerce_limit(max_words)
    if max_words <= 0:
        return text, False
    count = 0
    for match in re.finditer(r"\S+", text):
        token = match.group(0)
        if not any(ch.isalnum() for ch in token):
            continue
        count += 1
        if count > max_words:
            return _trim_ellipsis_source(text[: match.start()]), True
    if count <= max_words:
        return text, False
    return text, False


def _limit_chars(text: str, max_chars: int) -> tuple[str, bool]:
    max_chars = _coerce_limit(max_chars)
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    candidate = text[:max_chars]
    while candidate and unicodedata.combining(candidate[-1]):
        candidate = candidate[:-1]
    return candidate, True


def smart_title_case_subject(text: str) -> str:
    """Title-case subject text while preserving contractions and acronyms."""
    if not text:
        return text

    def convert(match: re.Match[str]) -> str:
        word = match.group(0)
        if not word:
            return word
        if word.isupper() and len(word) > 1:
            return word
        if any(ch.isdigit() for ch in word) and any(ch.isalpha() for ch in word):
            return word
        if any(ch.isupper() for ch in word[1:]) and not word.isupper():
            return word
        if word.lower() == "i":
            return "I"
        return word[:1].upper() + word[1:].lower()

    return _TITLE_WORD_RE.sub(convert, text)


def _smart_title_case(text: str) -> str:
    """Backward-compatible alias for Gmail subject title casing."""
    return smart_title_case_subject(text)


def shorten_subject(raw: str, max_words: int = 4, max_chars: int = 0) -> str:
    """Shorten a subject by word and/or character budget before pixel elision."""
    text = _clean_spaces(raw)
    if not text:
        return ""

    word_limit = _coerce_limit(max_words)
    char_limit = _coerce_limit(max_chars)

    if word_limit <= 0 and char_limit <= 0:
        return text
    if char_limit <= 0:
        candidate, shortened = _limit_words(text, word_limit)
        return _append_ellipsis(candidate, shortened)
    if word_limit <= 0:
        candidate, shortened = _limit_chars(text, char_limit)
        return _append_ellipsis(candidate, shortened)
    if len(text) <= char_limit:
        return text

    word_candidate, word_shortened = _limit_words(text, word_limit)
    char_candidate, char_shortened = _limit_chars(text, char_limit)
    if len(word_candidate) <= char_limit:
        candidate = word_candidate if len(word_candidate) >= len(char_candidate) else char_candidate
    else:
        candidate = char_candidate
    shortened = candidate != text or word_shortened or char_shortened
    return _append_ellipsis(candidate, shortened)


def _sender_from_address(address: str) -> str:
    local, _, domain = address.partition("@")
    local = local.strip()
    domain = domain.strip()
    local_key = local.lower().replace("_", "-")
    if domain and (not local or local_key in _NOISY_LOCAL_PARTS):
        return domain.split(".", 1)[0] or domain
    return local or domain or address


def title_case_sender_name(text: str) -> str:
    """Make sender display names start cleanly without crushing brand casing."""
    if not text:
        return text

    def convert(match: re.Match[str]) -> str:
        word = match.group(0)
        if not word:
            return word
        if word.isupper() and len(word) > 1:
            return word
        if any(ch.isupper() for ch in word[1:]):
            return word
        return word[:1].upper() + word[1:]

    return _SENDER_WORD_RE.sub(convert, text, count=1)


def _safe_chop(candidate: str, marker: str) -> str:
    if len(candidate.strip()) <= 3:
        return candidate
    idx = candidate.find(marker)
    if idx <= 0:
        return candidate
    chopped = candidate[:idx].strip()
    return chopped or candidate


def clean_sender_name(raw: str, enabled: bool = True, max_words: int = 3) -> str:
    """Clean noisy sender strings without destroying short/personal names."""
    text = _clean_spaces(_decode_mime_header(str(raw or "")))
    if not text:
        return ""
    if not enabled:
        candidate = text
    else:
        display_name, address = parseaddr(text)
        if display_name:
            candidate = _clean_spaces(display_name)
        elif "@" in address:
            candidate = _sender_from_address(address)
        else:
            candidate = text
        if len(candidate) > 1 and candidate[0] == candidate[-1] and candidate[0] in {"'", '"'}:
            candidate = candidate[1:-1].strip()
        candidate = _safe_chop(candidate, "<")
        for marker in (" - ", " – ", " — "):
            candidate = _safe_chop(candidate, marker)
        via_match = re.search(r"\s+via\s+.+$", candidate, flags=re.IGNORECASE)
        if via_match and via_match.start() > 0:
            candidate = candidate[: via_match.start()].strip() or candidate
        candidate = _clean_spaces(candidate).rstrip(".,;:")
    candidate = title_case_sender_name(candidate)
    candidate, shortened = _limit_words(candidate, max_words)
    return _append_ellipsis(candidate, shortened)


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
        "provider": email.provider,
        "account_email": email.account_email,
        "imap_uid": email.imap_uid,
        "rfc822_message_id": email.rfc822_message_id,
        "gmail_thread_id": email.gmail_thread_id,
        "gmail_message_id": email.gmail_message_id,
        "open_url": email.open_url,
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
            provider=data.get("provider", "gmail_api"),
            account_email=data.get("account_email"),
            imap_uid=data.get("imap_uid"),
            rfc822_message_id=data.get("rfc822_message_id"),
            gmail_thread_id=data.get("gmail_thread_id"),
            gmail_message_id=data.get("gmail_message_id"),
            open_url=data.get("open_url"),
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("[GMAIL] Failed to deserialize cached email: %s", e)
        return None


@dataclass(frozen=True)
class DisplayRow:
    """A single row in the Gmail widget — either one email or a group of threads.

    When ``count > 1`` the row represents a collapsed thread group.
    ``email`` is always the *most recent* message in the group (the one whose
    URL should be opened on click).
    """
    email: EmailMetadata
    count: int = 1


def _normalize_subject(subject: str) -> str:
    """Strip common reply/forward prefixes and collapse whitespace for grouping."""
    text = re.sub(r"^(?:(?:re|fw|fwd)\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
    return re.sub(r"\s+", " ", text).lower()


def group_emails(emails: List[EmailMetadata]) -> List[DisplayRow]:
    """Group emails by (normalised_sender_address, normalised_subject).

    Within each group the most recent email (by date) becomes the
    representative row.  Groups are returned sorted most-recent-first,
    matching the natural inbox order.
    """
    if not emails:
        return []
    groups: dict[str, list[EmailMetadata]] = {}
    for email in emails:
        _, addr = parseaddr(email.sender)
        key = (addr.lower().strip(), _normalize_subject(email.subject))
        groups.setdefault(str(key), []).append(email)
    rows: List[DisplayRow] = []
    for members in groups.values():
        members.sort(key=lambda e: e.date, reverse=True)
        rows.append(DisplayRow(email=members[0], count=len(members)))
    rows.sort(key=lambda r: r.email.date, reverse=True)
    return rows


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
