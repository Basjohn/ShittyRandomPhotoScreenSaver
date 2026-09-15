"""Shared policy helpers for service-backed retained widget runtimes.

Recurring cadence is intentionally *not* owned here. Weather, Media, Gmail,
and Steam obtain recurring timers only through ``widgets.overlay_timers`` and
the shared ``ThreadManager`` scheduler. This module stays presentation-neutral
and contains no local Qt timer/widget compatibility fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

from core.runtime_flags import automatic_service_updates_enabled


SERVICE_STARTUP_CACHE_FRESH_WINDOW = timedelta(minutes=15)


class StartupRefreshDecision(NamedTuple):
    run: bool
    reason: str
    age: timedelta | None


def should_run_automatic_startup_refresh(
    *,
    cache_timestamp: datetime | None = None,
    fresh_window: timedelta = SERVICE_STARTUP_CACHE_FRESH_WINDOW,
) -> bool:
    """Return True when automatic startup retrieval should run."""

    return get_automatic_startup_refresh_decision(
        cache_timestamp=cache_timestamp,
        fresh_window=fresh_window,
    ).run


def get_automatic_startup_refresh_decision(
    *,
    cache_timestamp: datetime | None = None,
    fresh_window: timedelta = SERVICE_STARTUP_CACHE_FRESH_WINDOW,
) -> StartupRefreshDecision:
    """Return the startup-refresh policy decision plus an auditable reason.

    ``--noupdates`` disables automatic service retrieval. Otherwise a fresh
    cache suppresses only the startup fetch; periodic cadence remains owned by
    the service's shared ThreadManager timer authority.
    """

    if not automatic_service_updates_enabled():
        return StartupRefreshDecision(False, "automatic_updates_disabled", None)
    if cache_timestamp is None:
        return StartupRefreshDecision(True, "missing_cache_timestamp", None)
    try:
        age = datetime.now() - cache_timestamp
    except Exception:
        return StartupRefreshDecision(True, "cache_timestamp_error", None)
    if age >= fresh_window:
        return StartupRefreshDecision(True, "cache_stale", age)
    return StartupRefreshDecision(False, "cache_fresh", age)
