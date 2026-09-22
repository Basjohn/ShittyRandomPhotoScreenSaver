"""RSS/Atom bytes -> durable normalized feed document.

Parsing is intentionally transport-free.  Feed validity never depends on image
presence: images are optional presentation candidates layered on valid items.
"""
from __future__ import annotations

import calendar
import mimetypes
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping

import feedparser

from .models import FeedDocument, FeedEnclosure, FeedImageCandidate, FeedItem
from .normalization import (
    display_title,
    normalized_action_url,
    normalized_media_url,
    plain_text,
    stable_item_id,
)


class FeedParseError(ValueError):
    pass


class _ImageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "img":
            return
        mapping = {str(k).casefold(): v for k, v in attrs}
        url = normalized_media_url(mapping.get("src") or mapping.get("data-src"))
        if url:
            self.urls.append(url)


def _published_at(entry: Mapping[str, Any]) -> int | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            try:
                result = int(calendar.timegm(value))
            except (TypeError, ValueError, OverflowError):
                continue
            if 0 < result < 4_102_444_800:
                return result
    return None


def _action_url(entry: Mapping[str, Any], *, base_url: str) -> str:
    direct = normalized_action_url(entry.get("link"), base_url=base_url)
    if direct:
        return direct
    links = entry.get("links")
    if isinstance(links, Iterable) and not isinstance(links, (str, bytes, Mapping)):
        fallback = ""
        for row in links:
            if not isinstance(row, Mapping):
                continue
            candidate = normalized_action_url(row.get("href"), base_url=base_url)
            if not candidate:
                continue
            relation = str(row.get("rel") or "").casefold()
            if relation in {"alternate", "via", ""}:
                return candidate
            fallback = fallback or candidate
        return fallback
    return ""


def _positive_int(value: object) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _append_image(
    result: list[FeedImageCandidate], seen: set[str], *, url: object,
    mime_type: object = "", width: object = None, height: object = None,
    relation: str, base_url: str = "",
) -> None:
    normalized = normalized_media_url(url, base_url=base_url)
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    result.append(FeedImageCandidate(
        url=normalized,
        mime_type=str(mime_type or "")[:120],
        width=_positive_int(width),
        height=_positive_int(height),
        relation=relation,
    ))


def _images(entry: Mapping[str, Any], *, base_url: str) -> tuple[FeedImageCandidate, ...]:
    result: list[FeedImageCandidate] = []
    seen: set[str] = set()

    for key, relation in (("media_thumbnail", "thumbnail"), ("media_content", "media")):
        rows = entry.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows[:12]:
            if not isinstance(row, Mapping):
                continue
            medium = str(row.get("medium") or "").casefold()
            mime_type = str(row.get("type") or "")
            if medium and medium != "image" and not mime_type.casefold().startswith("image/"):
                continue
            _append_image(
                result, seen, url=row.get("url"), mime_type=mime_type,
                width=row.get("width"), height=row.get("height"), relation=relation, base_url=base_url,
            )

    links = entry.get("links")
    if isinstance(links, list):
        for row in links[:20]:
            if not isinstance(row, Mapping):
                continue
            mime_type = str(row.get("type") or "")
            if str(row.get("rel") or "").casefold() == "enclosure" and mime_type.casefold().startswith("image/"):
                _append_image(result, seen, url=row.get("href"), mime_type=mime_type, relation="enclosure", base_url=base_url)

    for key in ("summary", "description"):
        raw = entry.get(key)
        if not raw:
            continue
        collector = _ImageCollector()
        try:
            collector.feed(str(raw)[:32768])
        except (ValueError, AssertionError):
            continue
        for url in collector.urls[:8]:
            _append_image(result, seen, url=url, relation="html", base_url=base_url)

    content = entry.get("content")
    if isinstance(content, list):
        for row in content[:4]:
            if not isinstance(row, Mapping):
                continue
            collector = _ImageCollector()
            try:
                collector.feed(str(row.get("value") or "")[:32768])
            except (ValueError, AssertionError):
                continue
            for url in collector.urls[:8]:
                _append_image(result, seen, url=url, relation="content", base_url=base_url)

    return tuple(result[:16])


def _enclosures(entry: Mapping[str, Any], *, base_url: str) -> tuple[FeedEnclosure, ...]:
    result: list[FeedEnclosure] = []
    seen: set[str] = set()
    rows: list[Mapping[str, Any]] = []
    for value in (entry.get("enclosures"), entry.get("links")):
        if isinstance(value, list):
            rows.extend(row for row in value[:20] if isinstance(row, Mapping))
    for row in rows:
        if row.get("rel") not in {None, "", "enclosure"} and row not in (entry.get("enclosures") or []):
            continue
        url = normalized_action_url(row.get("href") or row.get("url"), base_url=base_url)
        if not url or url in seen:
            continue
        mime_type = str(row.get("type") or mimetypes.guess_type(url)[0] or "")[:120]
        if mime_type.casefold().startswith("image/"):
            continue
        seen.add(url)
        result.append(FeedEnclosure(
            url=url,
            mime_type=mime_type,
            length=_positive_int(row.get("length")),
        ))
    return tuple(result[:8])


def parse_feed_bytes(payload: bytes, *, source_url: str, max_items: int = 50) -> FeedDocument:
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise FeedParseError("feed payload is empty")
    limit = max(1, min(200, int(max_items)))
    parsed = feedparser.parse(bytes(payload))
    raw_entries = getattr(parsed, "entries", ())
    if not raw_entries:
        bozo = getattr(parsed, "bozo_exception", None)
        detail = type(bozo).__name__ if bozo is not None else "no entries"
        raise FeedParseError(f"feed has no usable entries ({detail})")

    items: list[FeedItem] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if len(items) >= limit:
            break
        if not isinstance(raw, Mapping):
            continue
        action_url = _action_url(raw, base_url=source_url)
        published_at = _published_at(raw)
        title = display_title(raw.get("title"), fallback_url=action_url)
        item_id = stable_item_id(
            explicit_id=raw.get("id") or raw.get("guid"),
            action_url=action_url,
            title=title,
            published_at=published_at,
        )
        if item_id in seen:
            continue
        seen.add(item_id)
        summary = plain_text(raw.get("summary") or raw.get("description"), limit=1200)
        items.append(FeedItem(
            item_id=item_id,
            title=title,
            action_url=action_url,
            summary=summary,
            author=plain_text(raw.get("author"), limit=160),
            published_at=published_at,
            images=_images(raw, base_url=source_url),
            enclosures=_enclosures(raw, base_url=source_url),
        ))

    if not items:
        raise FeedParseError("feed entries could not be normalized")
    feed = getattr(parsed, "feed", {})
    feed_map = feed if isinstance(feed, Mapping) else {}
    home_url = normalized_action_url(feed_map.get("link"), base_url=source_url)
    format_name = str(getattr(parsed, "version", "") or "unknown")[:40]
    return FeedDocument(
        title=display_title(feed_map.get("title"), fallback_url=home_url or source_url),
        home_url=home_url,
        format=format_name,
        items=tuple(items),
    )
