"""Pure NASA Images API search/asset normalization, without HTTP or guessing URLs."""
from __future__ import annotations

import json
from urllib.parse import quote, urlparse

from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem
from core.feeds.normalization import normalized_media_url, plain_text


def nasa_image_listing(payload: bytes, source_url: str, max_items: int) -> FeedDocument | None:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    collection = data.get("collection") if isinstance(data, dict) else None
    if not isinstance(collection, dict) or not isinstance(collection.get("items"), list):
        return None
    rows = collection["items"][:max(1, min(200, max_items))]
    items = []
    if urlparse(source_url).path.startswith("/search"):
        for row in rows:
            if not isinstance(row, dict):
                continue
            metadata = row.get("data")
            if not isinstance(metadata, list) or not metadata or not isinstance(metadata[0], dict):
                continue
            metadata = metadata[0]
            nasa_id = metadata.get("nasa_id")
            title = plain_text(metadata.get("title"), limit=240)
            if (metadata.get("media_type") != "image" or not isinstance(nasa_id, str)
                    or not nasa_id or len(nasa_id) > 256 or not title
                    or any(word in title.casefold() for word in ("animation", "movie", "video"))):
                continue
            # The documented manifest endpoint uses the returned ID. Original
            # file paths are taken only from that manifest, never constructed.
            items.append(FeedItem(nasa_id, title, "https://images-api.nasa.gov/asset/" + quote(nasa_id, safe="")))
        return FeedDocument("NASA Images search", source_url, "nasa-search", tuple(items)) if items else None
    if not urlparse(source_url).path.startswith("/asset/"):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = normalized_media_url(row.get("href"), base_url=source_url)
        path = urlparse(url).path.casefold()
        if "/image/" not in path or "~orig." not in path or not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        items.append(FeedItem(url, "NASA original image", source_url, images=(FeedImageCandidate(url, relation="original"),)))
    return FeedDocument("NASA Images asset", source_url, "nasa-asset", tuple(items)) if items else None
