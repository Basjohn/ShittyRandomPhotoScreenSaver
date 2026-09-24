"""Feed bytes -> durable normalized feed document.

RSS 0.9x/1.0/2.0 and Atom go through ``feedparser``; a JSON document (JSON
Feed 1.x or a JF2 feed) goes through ``core.feeds.json_feed``. Every format
lands in the same ``FeedDocument`` model with the same title/summary rules.

Parsing is intentionally transport-free.  Feed validity never depends on image
presence: images are optional presentation candidates layered on valid items.
"""
from __future__ import annotations

import calendar
import mimetypes
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree

import feedparser

from .models import FeedDocument, FeedEnclosure, FeedImageCandidate, FeedItem
from .normalization import (
    display_title,
    entry_title_and_summary,
    normalized_action_url,
    normalized_media_url,
    plain_text,
    stable_item_id,
)


class FeedParseError(ValueError):
    pass


class FeedEmptyError(FeedParseError):
    """A recognised RSS/Atom document that currently has no usable entries.

    Distinct from a payload that is not a feed at all (an HTML page, an error
    body): an empty feed is still the right endpoint, so it must not trigger
    feed discovery; it is an ordinary retained-last-good source failure.
    """


class _ImageCollector(HTMLParser):
    def __init__(self, *, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = str(base_url or "")
        self.urls: list[str] = []

    def _srcset_candidates(self, value: object) -> list[str]:
        if not isinstance(value, str):
            return []
        rows: list[tuple[float, str]] = []
        for raw in value.split(",")[:12]:
            parts = raw.strip().split()
            if not parts:
                continue
            url = normalized_media_url(parts[0], base_url=self.base_url)
            if not url:
                continue
            weight = 1.0
            if len(parts) > 1:
                descriptor = parts[1].strip().lower()
                try:
                    if descriptor.endswith("w"):
                        weight = float(descriptor[:-1])
                    elif descriptor.endswith("x"):
                        weight = float(descriptor[:-1]) * 1000.0
                except ValueError:
                    pass
            rows.append((weight, url))
        return [url for _, url in sorted(rows, reverse=True)]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # ``ElementTree`` serializes namespaced XHTML as e.g. ``html:img``.
        # Treat the local name exactly like the ordinary HTML spelling so raw
        # Atom XHTML and RSS CDATA use the same candidate collector.
        kind = tag.casefold().rsplit(":", 1)[-1]
        if kind not in {"img", "source"}:
            return
        mapping = {str(k).casefold(): v for k, v in attrs}
        if kind == "img":
            for key in ("src", "data-src", "data-lazy-src", "data-original"):
                url = normalized_media_url(mapping.get(key), base_url=self.base_url)
                if url and url not in self.urls:
                    self.urls.append(url)
        for key in ("srcset", "data-srcset"):
            for url in self._srcset_candidates(mapping.get(key)):
                if url not in self.urls:
                    self.urls.append(url)


def html_image_urls(markup: object, *, base_url: str = "", limit: int = 8) -> list[str]:
    """Image candidates inside an HTML fragment (``img``/``source``, lazy and srcset)."""
    collector = _ImageCollector(base_url=base_url)
    try:
        collector.feed(str(markup or "")[:32768])
    except (ValueError, AssertionError):
        return []
    return collector.urls[: max(0, int(limit))]


_UTF8_BOM = bytes((0xEF, 0xBB, 0xBF))


def _is_json_document(payload: bytes) -> bool:
    return payload[:256].removeprefix(_UTF8_BOM).lstrip().startswith(b"{")


def _xml_local_name(tag: object) -> str:
    value = str(tag or "")
    return value.rsplit("}", 1)[-1].rsplit(":", 1)[-1].casefold()


def _element_inner_markup(element: ElementTree.Element) -> str:
    """Return bounded inner markup without making XML parsing an authority.

    ``feedparser`` is still the feed/model authority.  This tiny raw-markup
    companion exists only because feedparser sanitization may legitimately strip
    modern image hints such as ``source/srcset`` and lazy ``data-*`` attributes
    before the normalized entry mapping reaches :func:`_images`.
    """

    chunks: list[str] = []
    if element.text:
        chunks.append(str(element.text))
    for child in list(element):
        try:
            chunks.append(ElementTree.tostring(child, encoding="unicode"))
        except (TypeError, ValueError):
            continue
        if child.tail:
            chunks.append(str(child.tail))
    return "".join(chunks)[:32768]


def _raw_entry_image_markup(payload: bytes) -> tuple[tuple[str, ...], ...]:
    """Extract only per-entry HTML/XHTML fields needed for image discovery.

    The result is ordinal and deliberately presentation-neutral.  Parse failure
    simply yields no companion markup; it never changes whether feedparser
    accepts the document or how titles/actions/timestamps are normalized.
    """

    try:
        root = ElementTree.fromstring(bytes(payload))
    except (ElementTree.ParseError, TypeError, ValueError):
        return ()

    entries = [
        element for element in root.iter()
        if _xml_local_name(element.tag) in {"item", "entry"}
    ]
    result: list[tuple[str, ...]] = []
    markup_names = {"summary", "description", "content", "encoded"}
    for entry in entries:
        fragments: list[str] = []
        for element in entry.iter():
            if element is entry or _xml_local_name(element.tag) not in markup_names:
                continue
            markup = _element_inner_markup(element)
            if markup:
                fragments.append(markup)
            if len(fragments) >= 8:
                break
        result.append(tuple(fragments))
    return tuple(result)


def _summary_markup(entry: Mapping[str, Any]) -> object:
    """Summary/description, else the first content body (``content:encoded``-only items)."""
    direct = entry.get("summary") or entry.get("description")
    if direct:
        return direct
    content = entry.get("content")
    if isinstance(content, list):
        for row in content[:4]:
            if isinstance(row, Mapping) and row.get("value"):
                return row.get("value")
    return ""


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


def _images(
    entry: Mapping[str, Any], *, base_url: str,
    raw_markup: Iterable[str] = (),
) -> tuple[FeedImageCandidate, ...]:
    result: list[FeedImageCandidate] = []
    seen: set[str] = set()

    # Podcast episode art (``itunes:image`` / Podcasting 2.0) on the item.
    episode_art = entry.get("image")
    if isinstance(episode_art, Mapping):
        _append_image(result, seen, url=episode_art.get("href") or episode_art.get("url"),
                      relation="episode", base_url=base_url)

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

    # Feedparser sanitization is allowed to remove lazy/srcset attributes from
    # summary/content.  Recover those candidates from the already-downloaded XML
    # bytes before looking at the sanitized mapping.  This performs no network
    # work and preserves the same per-entry candidate order.
    for markup in raw_markup:
        collector = _ImageCollector(base_url=base_url)
        try:
            collector.feed(str(markup)[:32768])
        except (ValueError, AssertionError):
            continue
        for url in collector.urls[:8]:
            _append_image(result, seen, url=url, relation="html", base_url=base_url)

    for key in ("summary", "description"):
        raw = entry.get(key)
        if not raw:
            continue
        collector = _ImageCollector(base_url=base_url)
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
            collector = _ImageCollector(base_url=base_url)
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
    payload_bytes = bytes(payload)
    if _is_json_document(payload_bytes):
        from .json_feed import parse_json_feed_bytes
        return parse_json_feed_bytes(payload_bytes, source_url=source_url, max_items=limit)
    # Most feeds do not need a second XML pass. Only invoke the bounded raw
    # companion when the payload advertises image attributes that feedparser's
    # sanitizer may remove; ordinary normalized feed parsing remains the hot
    # path for everything else.
    image_markup_probe = payload_bytes.lower()
    needs_raw_image_markup = any(marker in image_markup_probe for marker in (
        b"srcset", b"data-src", b"data-lazy-src", b"data-original",
    ))
    raw_entry_markup = (
        _raw_entry_image_markup(payload_bytes) if needs_raw_image_markup else ()
    )
    parsed = feedparser.parse(payload_bytes)
    raw_entries = getattr(parsed, "entries", ())
    if not raw_entries:
        bozo = getattr(parsed, "bozo_exception", None)
        detail = type(bozo).__name__ if bozo is not None else "no entries"
        if getattr(parsed, "version", ""):
            raise FeedEmptyError(f"feed has no usable entries ({detail})")
        raise FeedParseError(f"feed has no usable entries ({detail})")

    items: list[FeedItem] = []
    seen: set[str] = set()
    for raw_index, raw in enumerate(raw_entries):
        if len(items) >= limit:
            break
        if not isinstance(raw, Mapping):
            continue
        action_url = _action_url(raw, base_url=source_url)
        published_at = _published_at(raw)
        summary = plain_text(_summary_markup(raw), limit=1200)
        title, summary = entry_title_and_summary(raw.get("title"), summary=summary, action_url=action_url)
        item_id = stable_item_id(
            explicit_id=raw.get("id") or raw.get("guid"),
            action_url=action_url,
            title=title,
            published_at=published_at,
        )
        if item_id in seen:
            continue
        seen.add(item_id)
        items.append(FeedItem(
            item_id=item_id,
            title=title,
            action_url=action_url,
            summary=summary,
            author=plain_text(raw.get("author"), limit=160),
            published_at=published_at,
            images=_images(
                raw,
                base_url=action_url or source_url,
                raw_markup=(
                    raw_entry_markup[raw_index]
                    if raw_index < len(raw_entry_markup) else ()
                ),
            ),
            enclosures=_enclosures(raw, base_url=action_url or source_url),
        ))

    if not items:
        raise FeedEmptyError("feed entries could not be normalized")
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
