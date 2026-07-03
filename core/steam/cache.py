"""Versioned atomic cache helpers for Steam fixture/backend results."""
from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.logging.logger import get_logger
from core.settings.storage_paths import get_steam_cache_dir
from core.steam.credentials import derive_profile_cache_key
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId

logger = get_logger(__name__)

STEAM_CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SteamCacheRecord:
    """Versioned cache envelope kept separate from user settings."""

    cache_key: str
    source_id: SteamSourceId
    payload: Mapping[str, Any]
    fetched_at: float
    attempted_sources: tuple[SteamSourceId, ...] = ()
    schema_version: int = STEAM_CACHE_SCHEMA_VERSION

    def to_json_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cache_key": self.cache_key,
            "source_id": self.source_id.value,
            "attempted_sources": [source.value for source in self.attempted_sources],
            "fetched_at": float(self.fetched_at),
            "payload": dict(self.payload),
        }


def cache_path_for(
    profile_identifier: str,
    cache_key: str,
    *,
    profile: str | None = None,
    root: Path | None = None,
) -> Path:
    """Return a safe account-private cache path without raw Steam identifiers."""
    safe_cache_key = _safe_cache_name(cache_key)
    if root is None:
        root = get_steam_cache_dir(
            profile=profile,
            profile_key=derive_profile_cache_key(profile_identifier),
        )
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe_cache_key}.json"


def write_cache_record(record: SteamCacheRecord, path: Path) -> Path:
    """Atomically write a Steam cache record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(record.to_json_payload(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        logger.info(
            "[STEAM] Cache write source=%s cache_key=%s attempted=%s",
            record.source_id.value,
            record.cache_key,
            ",".join(source.value for source in record.attempted_sources) or record.source_id.value,
        )
        return path
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.exception("[STEAM] Cache write failed cache_key=%s source=%s", record.cache_key, record.source_id.value)
        raise


def write_success_result(
    *,
    path: Path,
    cache_key: str,
    result: SteamResult,
    fetched_at: float | None = None,
) -> Path | None:
    """Persist a successful provider result; never freshen cache on failures."""
    if not result.ok or result.payload is None or result.source_id is None:
        logger.warning(
            "[STEAM] Cache no-write cache_key=%s status=%s source=%s",
            cache_key,
            result.status.value,
            result.source_id.value if result.source_id else "none",
        )
        return None
    return write_cache_record(
        SteamCacheRecord(
            cache_key=cache_key,
            source_id=result.source_id,
            payload=result.payload,
            fetched_at=time.time() if fetched_at is None else fetched_at,
            attempted_sources=result.attempted_sources,
        ),
        path,
    )


def read_cache_record(path: Path) -> SteamResult:
    """Read and validate a Steam cache record."""
    if not path.exists():
        return SteamResult(status=SteamResultStatus.CACHE_MISS, message="Steam cache file is missing.", from_cache=True)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("not an object")
        if raw.get("schema_version") != STEAM_CACHE_SCHEMA_VERSION:
            raise ValueError("unsupported schema")
        source_id = SteamSourceId(str(raw["source_id"]))
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("payload is not an object")
        attempted = tuple(SteamSourceId(str(item)) for item in raw.get("attempted_sources", []) if isinstance(item, str))
        return SteamResult(
            status=SteamResultStatus.SUCCESS,
            source_id=source_id,
            payload=dict(payload),
            attempted_sources=attempted or (source_id,),
            from_cache=True,
        )
    except Exception as exc:
        corrupt_path = path.with_name(f"{path.name}.corrupt")
        try:
            if path.exists():
                path.replace(corrupt_path)
        except Exception:
            pass
        logger.warning("[STEAM][FALLBACK] Corrupt Steam cache moved path=%s error=%s", path, exc)
        return SteamResult(
            status=SteamResultStatus.CACHE_CORRUPT,
            message="Steam cache file was corrupt.",
            from_cache=True,
        )


def _safe_cache_name(cache_key: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(cache_key).strip().lower())
    return cleaned[:80] or "steam_cache"
