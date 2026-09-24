"""JSON Feed 1.x and JF2 feeds -> the shared normalized feed model.

JSON Feed (https://jsonfeed.org, versions 1 and 1.1) is the JSON counterpart
of RSS/Atom; publishers serve it as ``application/feed+json`` or plain
``application/json``. JF2 (a W3C Social Web Working Group note) is the JSON
form of a microformats2 feed; ``core.feeds.hfeed`` also produces it from
IndieWeb h-feed pages, so both share the one mapping here.

Everything lands in the same ``FeedDocument`` as RSS/Atom with the same rules:
authored titles win, a title-less post takes its title from its own text, only
HTTP/S image candidates, bounded text, and no image is required.
"""
from __future__ import annotations

import json
import mimetypes
from typing import Any, Iterable, Mapping

from .models import FeedDocument, FeedEnclosure, FeedImageCandidate, FeedItem
from .normalization import (
    display_title,
    entry_title_and_summary,
    iso_timestamp,
    normalized_action_url,
    normalized_media_url,
    plain_text,
    stable_item_id,
)
from .parser import FeedEmptyError, FeedParseError, html_image_urls


_JSON_FEED_VERSION_PREFIXES = ("https://jsonfeed.org/version/", "http://jsonfeed.org/version/")
_MAX_IMAGES = 16
_MAX_ENCLOSURES = 8


def _text(value: object, *, limit: int = 8192) -> str:
    return str(value)[:limit] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def _rows(value: object, *, limit: int) -> list[Any]:
    if isinstance(value, list):
        return value[:limit]
    if value is None:
        return []
    return [value]


def _author_name(value: object) -> str:
    for row in _rows(value, limit=4):
        if isinstance(row, Mapping):
            name = plain_text(row.get("name"), limit=160)
        else:
            name = plain_text(_text(row), limit=160)
        if name:
            return name
    return ""


class _Images:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.rows: list[FeedImageCandidate] = []
        self._seen: set[str] = set()

    def add(self, url: object, *, relation: str, mime_type: object = "") -> None:
        if len(self.rows) >= _MAX_IMAGES:
            return
        normalized = normalized_media_url(_text(url), base_url=self.base_url)
        if normalized and normalized not in self._seen:
            self._seen.add(normalized)
            self.rows.append(FeedImageCandidate(
                url=normalized, mime_type=_text(mime_type, limit=120), relation=relation))

    def add_markup(self, markup: object, *, relation: str) -> None:
        for url in html_image_urls(_text(markup, limit=32768), base_url=self.base_url):
            self.add(url, relation=relation)


def _enclosure_rows(rows: Iterable[object], *, base_url: str, images: _Images) -> tuple[FeedEnclosure, ...]:
    result: list[FeedEnclosure] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        url = normalized_action_url(_text(row.get("url")), base_url=base_url)
        if not url or url in seen:
            continue
        mime_type = (_text(row.get("mime_type"), limit=120) or mimetypes.guess_type(url)[0] or "")[:120]
        if mime_type.casefold().startswith("image/"):
            images.add(url, relation="enclosure", mime_type=mime_type)
            continue
        size = row.get("size_in_bytes")
        seen.add(url)
        result.append(FeedEnclosure(
            url=url, mime_type=mime_type,
            length=size if type(size) is int and size > 0 else None,
        ))
        if len(result) >= _MAX_ENCLOSURES:
            break
    return tuple(result)


def _build_item(
    *, explicit_id: object, raw_title: object, action_url: str, summary_markup: object,
    published_at: int | None, author: str, images: _Images, enclosures: tuple[FeedEnclosure, ...],
) -> FeedItem:
    summary = plain_text(summary_markup, limit=1200)
    title, summary = entry_title_and_summary(raw_title, summary=summary, action_url=action_url)
    return FeedItem(
        item_id=stable_item_id(
            explicit_id=_text(explicit_id, limit=2048),
            action_url=action_url, title=title, published_at=published_at,
        ),
        title=title,
        action_url=action_url,
        summary=summary,
        author=author,
        published_at=published_at,
        images=tuple(images.rows),
        enclosures=enclosures,
    )


def _finish(title: object, *, home_url: str, source_url: str, fmt: str, items: list[FeedItem]) -> FeedDocument:
    if not items:
        raise FeedEmptyError(f"{fmt} feed has no usable items")
    return FeedDocument(
        title=display_title(title, fallback_url=home_url or source_url),
        home_url=home_url,
        format=fmt,
        items=tuple(items),
    )


def _json_feed(data: Mapping[str, Any], version: str, *, source_url: str, limit: int) -> FeedDocument:
    home_url = normalized_action_url(_text(data.get("home_page_url")), base_url=source_url)
    rows = data.get("items")
    if not isinstance(rows, list):
        raise FeedParseError("JSON Feed has no items list")
    feed_author = _author_name(data.get("authors")) or _author_name(data.get("author"))
    items: list[FeedItem] = []
    seen: set[str] = set()
    for row in rows[: limit * 4]:
        if len(items) >= limit:
            break
        if not isinstance(row, Mapping):
            continue
        action_url = (
            normalized_action_url(_text(row.get("url")), base_url=source_url)
            or normalized_action_url(_text(row.get("external_url")), base_url=source_url)
        )
        base_url = action_url or source_url
        images = _Images(base_url)
        images.add(row.get("image"), relation="feed")
        images.add(row.get("banner_image"), relation="banner")
        enclosures = _enclosure_rows(_rows(row.get("attachments"), limit=20), base_url=base_url, images=images)
        images.add_markup(row.get("content_html"), relation="content")
        item = _build_item(
            explicit_id=row.get("id"),
            raw_title=_text(row.get("title"), limit=2000),
            action_url=action_url,
            summary_markup=(_text(row.get("summary"), limit=16384)
                            or _text(row.get("content_html"), limit=16384)
                            or _text(row.get("content_text"), limit=16384)),
            published_at=iso_timestamp(row.get("date_published")) or iso_timestamp(row.get("date_modified")),
            author=_author_name(row.get("authors")) or _author_name(row.get("author")) or feed_author,
            images=images,
            enclosures=enclosures,
        )
        if item.item_id not in seen:
            seen.add(item.item_id)
            items.append(item)
    tail = version.rstrip("/").rsplit("/", 1)[-1].replace(".", "")
    return _finish(data.get("title"), home_url=home_url, source_url=source_url,
                   fmt=f"json{tail}"[:40] if tail.isalnum() else "json", items=items)


def _jf2_content(value: object) -> tuple[str, str]:
    """``(markup_or_text, html)`` from a JF2 ``content`` (string or {html,text})."""
    if isinstance(value, Mapping):
        markup = _text(value.get("html"), limit=16384)
        return markup or _text(value.get("text"), limit=16384), markup
    return _text(value, limit=16384), ""


def jf2_feed_document(data: Mapping[str, Any], *, source_url: str, max_items: int, fmt: str = "jf2") -> FeedDocument:
    """A JF2 ``{"type": "feed", "children": [...]}`` document -> ``FeedDocument``."""
    limit = max(1, min(200, int(max_items)))
    home_url = normalized_action_url(_text(data.get("url")), base_url=source_url)
    feed_author = _author_name(data.get("author"))
    items: list[FeedItem] = []
    seen: set[str] = set()
    for row in _rows(data.get("children"), limit=limit * 4):
        if len(items) >= limit:
            break
        if not isinstance(row, Mapping) or str(row.get("type") or "entry") != "entry":
            continue
        urls = [normalized_action_url(_text(url), base_url=source_url)
                for url in _rows(row.get("url"), limit=4)]
        action_url = next((url for url in urls if url), "")
        base_url = action_url or source_url
        images = _Images(base_url)
        for key, relation in (("featured", "featured"), ("photo", "photo")):
            for url in _rows(row.get(key), limit=8):
                images.add(url.get("value") if isinstance(url, Mapping) else url, relation=relation)
        content, content_html = _jf2_content(row.get("content"))
        if content_html:
            images.add_markup(content_html, relation="content")
        enclosures = _enclosure_rows(
            ({"url": url} for key in ("video", "audio") for url in _rows(row.get(key), limit=4)),
            base_url=base_url, images=images,
        )
        item = _build_item(
            explicit_id=_text(row.get("uid")) or action_url,
            raw_title=_text(row.get("name"), limit=2000),
            action_url=action_url,
            summary_markup=_text(row.get("summary"), limit=16384) or content,
            published_at=iso_timestamp(row.get("published")) or iso_timestamp(row.get("updated")),
            author=_author_name(row.get("author")) or feed_author,
            images=images,
            enclosures=enclosures,
        )
        if item.item_id not in seen:
            seen.add(item.item_id)
            items.append(item)
    return _finish(data.get("name"), home_url=home_url, source_url=source_url, fmt=fmt, items=items)


def parse_json_feed_bytes(payload: bytes, *, source_url: str, max_items: int = 50) -> FeedDocument:
    """A JSON Feed 1.x or JF2 feed document; anything else is not a feed."""
    try:
        data = json.loads(bytes(payload).decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise FeedParseError(f"not a JSON document ({type(exc).__name__})") from exc
    if not isinstance(data, Mapping):
        raise FeedParseError("JSON document is not an object")
    limit = max(1, min(200, int(max_items)))
    version = _text(data.get("version"), limit=200)
    if version.startswith(_JSON_FEED_VERSION_PREFIXES):
        return _json_feed(data, version, source_url=source_url, limit=limit)
    if data.get("type") == "feed" and isinstance(data.get("children"), list):
        return jf2_feed_document(data, source_url=source_url, max_items=limit)
    raise FeedParseError("JSON document is not a JSON Feed or JF2 feed")


__all__ = ["jf2_feed_document", "parse_json_feed_bytes"]
