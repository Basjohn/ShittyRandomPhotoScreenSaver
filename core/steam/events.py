"""Narrow EventSystem publication helpers for Steam data updates."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.events.event_system import EventSystem
from core.steam.models import SteamResult, SteamSourceId

STEAM_DATA_READY_EVENT = "steam.data.ready"


def publish_steam_data_ready(
    event_system: EventSystem,
    *,
    source_id: SteamSourceId,
    profile_key: str,
    cache_key: str,
    result: SteamResult,
) -> None:
    """Publish a narrow, non-secret Steam data-ready event."""
    data: Mapping[str, Any] = {
        "source_id": source_id.value,
        "profile_key": profile_key,
        "cache_key": cache_key,
        "status": result.status.value,
        "from_cache": result.from_cache,
        "attempted_sources": [source.value for source in result.attempted_sources],
    }
    event_system.publish(STEAM_DATA_READY_EVENT, data=data, source="steam")
