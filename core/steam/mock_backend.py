"""Fixture-backed Steam backend for card and provider tests."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId


class SteamFixtureBackend:
    """Simple fixture backend that never performs network IO."""

    def __init__(self, fixtures: Mapping[SteamSourceId | str, Mapping[str, Any] | Path | str]) -> None:
        self._fixtures = dict(fixtures)
        self.requests: list[SteamSourceId] = []

    def fetch(self, source_id: SteamSourceId, **params: Any) -> SteamResult:
        self.requests.append(source_id)
        fixture = self._fixtures.get(source_id, self._fixtures.get(source_id.value))
        if fixture is None:
            return SteamResult(
                status=SteamResultStatus.CACHE_MISS,
                source_id=source_id,
                message="Steam fixture is missing.",
                attempted_sources=(source_id,),
            )
        if isinstance(fixture, Path):
            payload = json.loads(fixture.read_text(encoding="utf-8"))
        elif isinstance(fixture, str):
            payload = json.loads(fixture)
        else:
            payload = dict(fixture)
        return SteamResult(
            status=SteamResultStatus.SUCCESS,
            source_id=source_id,
            payload=payload,
            attempted_sources=(source_id,),
        )
