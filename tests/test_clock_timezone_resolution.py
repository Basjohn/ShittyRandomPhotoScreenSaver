"""Clock resolver timezone regression boundaries.

These use the Clock module's actual resolver rather than the settings combobox or
an independent timezone helper. They keep the retained Clock contract pinned to
the IANA rules currently supplied by the required ``pytz`` database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from rendering.quick.widgets.clock import _parse_timezone


def _converted(name: str, instant: datetime) -> datetime:
    zone = _parse_timezone(name)
    assert zone is not None, f"Clock resolver rejected persisted timezone {name!r}"
    return instant.astimezone(zone)


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
def test_clock_resolver_preserves_dst_and_non_dst_named_zone_rules(
    name: str,
    instant: datetime,
    wall_hour: int,
    offset: timedelta,
) -> None:
    converted = _converted(name, instant)
    assert converted.hour == wall_hour
    assert converted.utcoffset() == offset


@pytest.mark.parametrize(
    ("persisted_name", "instant", "expected_offset"),
    (
        ("US/Eastern", datetime(2026, 7, 15, 12, tzinfo=timezone.utc), -timedelta(hours=4)),
        ("Canada/Pacific", datetime(2026, 7, 15, 12, tzinfo=timezone.utc), -timedelta(hours=7)),
        ("Asia/Calcutta", datetime(2026, 1, 15, 12, tzinfo=timezone.utc), timedelta(hours=5, minutes=30)),
        ("Australia/NSW", datetime(2026, 1, 15, 12, tzinfo=timezone.utc), timedelta(hours=11)),
    ),
)
def test_clock_resolver_accepts_persisted_iana_aliases(
    persisted_name: str,
    instant: datetime,
    expected_offset: timedelta,
) -> None:
    assert _converted(persisted_name, instant).utcoffset() == expected_offset


def test_clock_resolver_keeps_troll_and_casablanca_database_rules() -> None:
    winter_troll = _converted("Antarctica/Troll", datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    summer_troll = _converted("Antarctica/Troll", datetime(2026, 7, 15, 12, tzinfo=timezone.utc))
    casablanca = _converted("Africa/Casablanca", datetime(2026, 10, 15, 12, tzinfo=timezone.utc))

    assert winter_troll.utcoffset() == timedelta(0)
    assert summer_troll.utcoffset() == timedelta(hours=2)
    assert casablanca.utcoffset() == timedelta(hours=1)
