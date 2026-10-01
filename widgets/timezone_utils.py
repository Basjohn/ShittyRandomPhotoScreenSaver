"""Timezone utilities for Clock settings and retained presentation.

Named-zone authority is QtCore.QTimeZone.  SRPSS already ships QtCore, so this
keeps current/DST-aware IANA handling without bundling pytz's world zoneinfo
payload as hundreds of loose files.
"""
from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from typing import List, Tuple

from PySide6.QtCore import QByteArray, QTimeZone

from core.logging.logger import get_logger

logger = get_logger(__name__)


# Persisted aliases from SRPSS' historical pytz-backed choices.  QTimeZone can
# resolve many of these directly; the bounded map preserves the app-authored
# legacy surface on Windows even when the native backend exposes only canonical
# IANA IDs.
_LEGACY_IANA_ALIASES = {
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "US/Alaska": "America/Anchorage",
    "US/Hawaii": "Pacific/Honolulu",
    "Canada/Eastern": "America/Toronto",
    "Canada/Central": "America/Winnipeg",
    "Canada/Mountain": "America/Edmonton",
    "Canada/Pacific": "America/Vancouver",
    "Asia/Calcutta": "Asia/Kolkata",
    "Australia/NSW": "Australia/Sydney",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
}

_COMMON_NAMED_ZONES: tuple[tuple[str, str], ...] = (
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
)

_UTC_OFFSETS: tuple[tuple[str, str], ...] = (
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
)


def _qbytearray_text(value: QByteArray) -> str:
    try:
        return bytes(value).decode("utf-8", errors="strict")
    except (TypeError, UnicodeDecodeError):
        return ""


def _make_qtimezone(zone_id: str) -> QTimeZone | None:
    encoded = QByteArray(zone_id.encode("utf-8"))
    zone = QTimeZone(encoded)
    if zone.isValid():
        return zone

    # On Windows Qt maps IANA IDs through the native Windows zone database.
    # This path also canonicalizes aliases that are understood by Qt's CLDR map.
    windows_id = QTimeZone.ianaIdToWindowsId(encoded)
    if len(windows_id):
        canonical = QTimeZone.windowsIdToDefaultIanaId(windows_id)
        if len(canonical):
            zone = QTimeZone(canonical)
            if zone.isValid():
                return zone
    return None


def resolve_named_timezone(timezone_str: str) -> QTimeZone | None:
    """Resolve a named IANA/persisted alias through Qt's timezone backend."""

    normalized = str(timezone_str or "").strip()
    if not normalized:
        return None

    zone = _make_qtimezone(normalized)
    if zone is not None:
        return zone

    canonical = _LEGACY_IANA_ALIASES.get(normalized)
    if canonical:
        return _make_qtimezone(canonical)
    return None


def _parse_utc_offset(timezone_str: str) -> tzinfo | None:
    normalized = str(timezone_str or "").strip()
    if not normalized.upper().startswith("UTC"):
        return None

    suffix = normalized[3:]
    if suffix in {"", "+0", "-0", "+0:00", "-0:00"}:
        return timezone.utc

    try:
        sign = -1 if suffix.startswith("-") else 1
        if suffix[:1] in {"+", "-"}:
            suffix = suffix[1:]
        hour_text, separator, minute_text = suffix.partition(":")
        hours = int(hour_text)
        minutes = int(minute_text or "0") if separator else 0
        if not (0 <= minutes < 60):
            return None
        total_minutes = sign * (hours * 60 + minutes)
        if not (-12 * 60 <= total_minutes <= 14 * 60):
            return None
        return timezone(timedelta(minutes=total_minutes))
    except (TypeError, ValueError):
        return None


def resolve_timezone(timezone_str: str) -> QTimeZone | tzinfo | None:
    """Resolve SRPSS' persisted timezone contract without a bundled tzdata package."""

    normalized = str(timezone_str or "local").strip()
    if not normalized or normalized.lower() == "local":
        return None

    fixed = _parse_utc_offset(normalized)
    if fixed is not None:
        return fixed
    return resolve_named_timezone(normalized)


def get_local_timezone() -> str:
    """Return the system's real IANA identity when Qt can provide it."""

    try:
        zone = QTimeZone.systemTimeZone()
        if zone.isValid():
            zone_id = _qbytearray_text(zone.id())
            if zone_id:
                logger.info("Auto-detected timezone: %s", zone_id)
                return zone_id
    except Exception as exc:
        logger.warning("Failed to auto-detect timezone: %s", exc)
    return "local"


def get_common_timezones() -> List[Tuple[str, str]]:
    """Return the bounded Settings/Onboarding timezone catalogue."""

    return [
        ("Local Time", "local"),
        ("UTC", "UTC"),
        *_COMMON_NAMED_ZONES,
        *_UTC_OFFSETS,
    ]


def validate_timezone(timezone_str: str) -> bool:
    """Validate the local sentinel, explicit UTC offsets, or Qt-backed named zones."""

    normalized = str(timezone_str or "").strip()
    if not normalized or normalized.lower() == "local":
        return True
    return resolve_timezone(normalized) is not None
