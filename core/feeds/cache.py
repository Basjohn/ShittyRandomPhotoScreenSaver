"""Versioned atomic durable last-good cache for general feeds."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
import tempfile
from typing import Any, Mapping

from core.settings.storage_paths import detect_current_profile, get_feed_cache_dir

from .models import (
    FeedCacheRecord,
    FeedDocument,
    FeedEnclosure,
    FeedHealth,
    FeedImageCandidate,
    FeedItem,
    FeedSnapshot,
)
from .normalization import safe_cache_fragment


SCHEMA_VERSION = 1
MAX_CACHE_FILE_BYTES = 8 * 1024 * 1024


def _required_str(value: object, *, max_len: int) -> str:
    if type(value) is not str or not value or len(value) > max_len:
        raise ValueError("invalid cache string")
    return value


def _optional_str(value: object, *, max_len: int) -> str:
    if value is None:
        return ""
    if type(value) is not str or len(value) > max_len:
        raise ValueError("invalid cache string")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in {int, float}:
        raise ValueError("invalid cache number")
    result = float(value)
    if result < 0:
        raise ValueError("invalid cache number")
    return result


def _image(row: Mapping[str, Any]) -> FeedImageCandidate:
    return FeedImageCandidate(
        url=_required_str(row.get("url"), max_len=4096),
        mime_type=_optional_str(row.get("mime_type"), max_len=120),
        width=int(row["width"]) if type(row.get("width")) is int and row["width"] > 0 else None,
        height=int(row["height"]) if type(row.get("height")) is int and row["height"] > 0 else None,
        relation=_optional_str(row.get("relation"), max_len=40) or "feed",
    )


def _enclosure(row: Mapping[str, Any]) -> FeedEnclosure:
    return FeedEnclosure(
        url=_required_str(row.get("url"), max_len=8192),
        mime_type=_optional_str(row.get("mime_type"), max_len=120),
        length=int(row["length"]) if type(row.get("length")) is int and row["length"] > 0 else None,
    )


def _item(row: Mapping[str, Any]) -> FeedItem:
    raw_images = row.get("images", [])
    raw_enclosures = row.get("enclosures", [])
    if not isinstance(raw_images, list) or len(raw_images) > 16:
        raise ValueError("invalid cache images")
    if not isinstance(raw_enclosures, list) or len(raw_enclosures) > 8:
        raise ValueError("invalid cache enclosures")
    published = row.get("published_at")
    if published is not None and (type(published) is not int or not 0 < published < 4_102_444_800):
        raise ValueError("invalid cache timestamp")
    if any(not isinstance(item, Mapping) for item in raw_images):
        raise ValueError("invalid cache image row")
    if any(not isinstance(item, Mapping) for item in raw_enclosures):
        raise ValueError("invalid cache enclosure row")
    return FeedItem(
        item_id=_required_str(row.get("item_id"), max_len=128),
        title=_required_str(row.get("title"), max_len=300),
        action_url=_optional_str(row.get("action_url"), max_len=8192),
        summary=_optional_str(row.get("summary"), max_len=1200),
        author=_optional_str(row.get("author"), max_len=160),
        published_at=published,
        images=tuple(_image(item) for item in raw_images),
        enclosures=tuple(_enclosure(item) for item in raw_enclosures),
    )


def _document(row: Mapping[str, Any]) -> FeedDocument:
    items = row.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        raise ValueError("invalid cache items")
    if any(not isinstance(item, Mapping) for item in items):
        raise ValueError("invalid cache item row")
    resolved_items = tuple(_item(item) for item in items)
    if not resolved_items:
        raise ValueError("invalid cache items")
    return FeedDocument(
        title=_required_str(row.get("title"), max_len=300),
        home_url=_optional_str(row.get("home_url"), max_len=8192),
        format=_optional_str(row.get("format"), max_len=40) or "unknown",
        items=resolved_items,
    )


def _record(payload: Mapping[str, Any]) -> FeedCacheRecord:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported feed cache schema")
    raw_health = payload.get("health")
    if not isinstance(raw_health, Mapping):
        raise ValueError("missing feed cache health")
    health = FeedHealth(
        last_checked_at=_optional_float(raw_health.get("last_checked_at")),
        last_success_at=_optional_float(raw_health.get("last_success_at")),
        consecutive_failures=int(raw_health.get("consecutive_failures", 0))
            if type(raw_health.get("consecutive_failures", 0)) is int and raw_health.get("consecutive_failures", 0) >= 0
            else 0,
        last_failure=_optional_str(raw_health.get("last_failure"), max_len=240),
        backoff_until=_optional_float(raw_health.get("backoff_until")),
    )
    raw_snapshot = payload.get("snapshot")
    snapshot = None
    if raw_snapshot is not None:
        if not isinstance(raw_snapshot, Mapping):
            raise ValueError("invalid feed cache snapshot")
        raw_document = raw_snapshot.get("document")
        if not isinstance(raw_document, Mapping):
            raise ValueError("invalid feed cache document")
        fetched_at = _optional_float(raw_snapshot.get("fetched_at"))
        if fetched_at is None:
            raise ValueError("missing feed cache fetched time")
        snapshot = FeedSnapshot(document=_document(raw_document), fetched_at=fetched_at)
    return FeedCacheRecord(
        source_id=_required_str(payload.get("source_id"), max_len=160),
        endpoint_fingerprint=_required_str(payload.get("endpoint_fingerprint"), max_len=128),
        snapshot=snapshot,
        health=health,
        etag=_optional_str(payload.get("etag"), max_len=1024),
        last_modified=_optional_str(payload.get("last_modified"), max_len=1024),
        schema_version=SCHEMA_VERSION,
    )


class FeedCacheStore:
    def __init__(self, root: Path | None = None, *, profile: str | None = None) -> None:
        self.root = (
            Path(root) if root is not None
            else get_feed_cache_dir(profile or detect_current_profile())
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, cache_key: str) -> Path:
        return self.root / f"{safe_cache_fragment(cache_key)}.json"

    def read(self, cache_key: str) -> FeedCacheRecord | None:
        path = self.path_for(cache_key)
        try:
            if path.stat().st_size > MAX_CACHE_FILE_BYTES:
                raise ValueError("feed cache exceeds byte limit")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("feed cache root is not an object")
            return _record(payload)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._quarantine(path)
            return None

    def write(self, cache_key: str, record: FeedCacheRecord) -> Path:
        if record.schema_version != SCHEMA_VERSION:
            raise ValueError("refusing to write unsupported feed cache schema")
        path = self.path_for(cache_key)
        payload = asdict(record)
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) > MAX_CACHE_FILE_BYTES:
            raise ValueError("feed cache record exceeds byte limit")
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.root, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as handle:
                tmp = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
        return path

    def _quarantine(self, path: Path) -> None:
        try:
            corrupt = path.with_suffix(path.suffix + ".corrupt")
            corrupt.unlink(missing_ok=True)
            os.replace(path, corrupt)
        except OSError:
            pass
