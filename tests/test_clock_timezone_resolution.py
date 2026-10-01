"""Clock resolver timezone regression boundaries.

Named zones are resolved through QtCore.QTimeZone, which is already part of the
application runtime.  The contract keeps the bounded Settings catalogue,
current/DST-aware named zones, persisted SRPSS aliases, local detection and
explicit UTC offsets without shipping pytz's world zoneinfo tree.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rendering.quick.widgets.clock import _datetime_in_timezone, _parse_timezone


ROOT = Path(__file__).resolve().parents[1]


def _converted(name: str, instant: datetime) -> datetime:
    zone = _parse_timezone(name)
    assert zone is not None, f"Clock resolver rejected persisted timezone {name!r}"
    return _datetime_in_timezone(zone, instant)


def test_clock_resolver_keeps_local_sentinel_and_explicit_utc_offsets() -> None:
    assert _parse_timezone("local") is None
    assert _parse_timezone("  ") is None

    instant = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    assert _converted("UTC", instant).utcoffset() == timedelta(0)
    assert _converted("UTC-3:30", instant).utcoffset() == -timedelta(hours=3, minutes=30)
    assert _converted("UTC+5:45", instant).utcoffset() == timedelta(hours=5, minutes=45)


@pytest.mark.parametrize(
    ("name", "instant", "wall_hour", "offset"),
    (
        (
            "America/New_York",
            datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc),
            1,
            -timedelta(hours=5),
        ),
        (
            "America/New_York",
            datetime(2026, 3, 8, 7, 0, tzinfo=timezone.utc),
            3,
            -timedelta(hours=4),
        ),
        (
            "Africa/Johannesburg",
            datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
            14,
            timedelta(hours=2),
        ),
    ),
)
def test_clock_resolver_preserves_current_dst_and_non_dst_named_zone_rules(
    name: str,
    instant: datetime,
    wall_hour: int,
    offset: timedelta,
) -> None:
    converted = _converted(name, instant)
    assert converted.hour == wall_hour
    assert converted.utcoffset() == offset


@pytest.mark.parametrize(
    ("persisted_name", "canonical_name", "instant"),
    (
        ("US/Eastern", "America/New_York", datetime(2026, 7, 15, 12, tzinfo=timezone.utc)),
        ("Canada/Pacific", "America/Vancouver", datetime(2026, 7, 15, 12, tzinfo=timezone.utc)),
        ("Asia/Calcutta", "Asia/Kolkata", datetime(2026, 1, 15, 12, tzinfo=timezone.utc)),
        ("Australia/NSW", "Australia/Sydney", datetime(2026, 1, 15, 12, tzinfo=timezone.utc)),
    ),
)
def test_clock_resolver_keeps_bounded_persisted_alias_compatibility(
    persisted_name: str,
    canonical_name: str,
    instant: datetime,
) -> None:
    persisted = _converted(persisted_name, instant)
    canonical = _converted(canonical_name, instant)
    assert persisted.replace(tzinfo=None) == canonical.replace(tzinfo=None)
    assert persisted.utcoffset() == canonical.utcoffset()


def test_pytz_world_database_is_not_a_runtime_or_build_dependency() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    timezone_utils = (ROOT / "widgets" / "timezone_utils.py").read_text(encoding="utf-8").casefold()
    clock = (ROOT / "rendering" / "quick" / "widgets" / "clock.py").read_text(encoding="utf-8").casefold()

    assert "pytz==" not in requirements
    assert "import pytz" not in timezone_utils
    assert "import pytz" not in clock
    assert "qtimezone" in timezone_utils
    assert "systemtimezone" in timezone_utils
