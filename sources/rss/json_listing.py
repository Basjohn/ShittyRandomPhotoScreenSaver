"""Generic JSON image listings -> the shared feed model (wallpaper feeds only).

Some good wallpaper sources publish a JSON API listing rather than a feed. This
adapter reads any such listing by shape, never by site: the listing is the
longest array of objects within two levels of the document (wrappers such as
``{"kind": ..., "data": {...}}`` are unwrapped); each entry's images are its
string values that are HTTP(S) image URLs, on the entry itself or one object
below it; declared pixel sizes come from common key names (``width``/``height``,
``dimension_x``/``dimension_y``, a ``"3840x2160"`` resolution string). Declared
sizes describe the entry's own top-level image; nested variants (thumbnails)
come after it as unsized fallbacks. Every candidate is still verified from its
real header before it is kept, so a wrong guess costs a few kilobytes.

It is a ``FeedSource`` document adapter: it runs only on a structured payload
that is not a feed, and returns ``None`` when the payload is not a listing.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem
from core.feeds.normalization import (
    display_title,
    iso_timestamp,
    normalized_action_url,
    normalized_media_url,
    stable_item_id,
)

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
# Keys that name an image even when the URL has no extension.
_IMAGE_KEYS = frozenset({"image", "image_url", "img", "src", "path", "full", "original",
                         "raw", "download", "download_url", "photo", "picture"})
_WIDTH_KEYS = ("width", "dimension_x", "image_width", "original_width", "w")
_HEIGHT_KEYS = ("height", "dimension_y", "image_height", "original_height", "h")
_RESOLUTION_KEYS = ("resolution", "dimensions", "size")
_TITLE_KEYS = ("title", "name", "caption", "alt_description", "alt", "description")
_LINK_KEYS = ("url", "link", "permalink", "page_url", "html_url", "short_url")
_DATE_KEYS = ("created_at", "date_published", "published", "published_at", "date",
              "created", "created_utc", "updated_at")
_RESOLUTION_RE = re.compile(r"^\s*(\d{2,6})\s*[x×]\s*(\d{2,6})\s*$")
_MAX_ENTRIES = 500


def _listing(data: Any) -> list[dict]:
    found: list[list[dict]] = []

    def visit(node: Any, depth: int) -> None:
        if isinstance(node, list):
            rows = [row for row in node[:_MAX_ENTRIES] if isinstance(row, dict)]
            if rows:
                found.append(rows)
        elif isinstance(node, dict) and depth < 2:
            for value in node.values():
                visit(value, depth + 1)

    visit(data, 0)
    rows = max(found, key=len, default=[])
    # ``[{"kind": "t3", "data": {...}}]``-style wrappers: the object is the entry.
    if rows and all(len(row) <= 3 and isinstance(row.get("data"), dict) for row in rows):
        rows = [row["data"] for row in rows]
    return rows


def _is_image_url(key: str, value: str, base_url: str) -> str:
    url = normalized_media_url(value, base_url=base_url)
    if not url:
        return ""
    path = urlparse(url).path.casefold()
    return url if path.endswith(_IMAGE_EXTENSIONS) or key.casefold() in _IMAGE_KEYS else ""


def _number(row: dict, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = row.get(key)
        if type(value) in {int, float} and 0 < value < 1_000_000:
            return int(value)
    return None


def _declared_size(row: dict) -> tuple[int | None, int | None]:
    width, height = _number(row, _WIDTH_KEYS), _number(row, _HEIGHT_KEYS)
    if width and height:
        return width, height
    for key in _RESOLUTION_KEYS:
        match = _RESOLUTION_RE.match(str(row.get(key) or ""))
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def _entry_images(row: dict, base_url: str) -> tuple[FeedImageCandidate, ...]:
    width, height = _declared_size(row)
    own: list[str] = []
    nested: list[str] = []
    for key, value in row.items():
        if isinstance(value, str):
            url = _is_image_url(key, value, base_url)
            if url and url not in own:
                own.append(url)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                if isinstance(child, str):
                    url = _is_image_url(child_key, child, base_url)
                    if url and url not in own and url not in nested:
                        nested.append(url)
    candidates = [FeedImageCandidate(url, width=width, height=height, relation="listing") for url in own]
    candidates += [FeedImageCandidate(url, relation="listing-variant") for url in nested]
    return tuple(candidates[:16])


def _published(row: dict) -> int | None:
    for key in _DATE_KEYS:
        value = row.get(key)
        if type(value) in {int, float} and 0 < value < 4_102_444_800:
            return int(value)
        stamp = iso_timestamp(value)
        if stamp:
            return stamp
    return None


def json_image_listing(payload: bytes, source_url: str, max_items: int) -> FeedDocument | None:
    """An image listing as a ``FeedDocument``, or ``None`` when the payload is not one."""
    try:
        data = json.loads(bytes(payload).decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    rows = _listing(data)
    items: list[FeedItem] = []
    seen: set[str] = set()
    limit = max(1, min(200, int(max_items)))
    for row in rows:
        if len(items) >= limit:
            break
        images = _entry_images(row, source_url)
        if not images:
            continue
        link = next((normalized_action_url(str(row.get(key) or ""), base_url=source_url)
                     for key in _LINK_KEYS
                     if normalized_action_url(str(row.get(key) or ""), base_url=source_url)
                     and not urlparse(str(row.get(key))).path.casefold().endswith(_IMAGE_EXTENSIONS)), "")
        title = display_title(next((row.get(key) for key in _TITLE_KEYS if row.get(key)), None),
                              fallback_url=link or images[0].url)
        published = _published(row)
        item_id = stable_item_id(explicit_id=row.get("id"), action_url=link or images[0].url,
                                 title=title, published_at=published)
        if item_id in seen:
            continue
        seen.add(item_id)
        items.append(FeedItem(item_id=item_id, title=title, action_url=link,
                              published_at=published, images=images))
    if not items:
        return None
    host = urlparse(source_url).hostname or "listing"
    title = data.get("title") if isinstance(data, dict) and isinstance(data.get("title"), str) else host
    return FeedDocument(title=display_title(title, fallback_url=source_url),
                        home_url=urljoin(source_url, "/"), format="json-listing", items=tuple(items))


__all__ = ["json_image_listing"]
