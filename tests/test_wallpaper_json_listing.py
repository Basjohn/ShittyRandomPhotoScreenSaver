"""Generic JSON image listings read by shape (never by site) into the feed model."""
from __future__ import annotations

import json
from pathlib import Path

from core.feeds.cache import FeedCacheStore
from core.feeds.models import FeedSourceSpec
from core.feeds.source import FeedSource
from core.feeds.transport import FeedHttpResponse
from sources.rss.json_listing import json_image_listing


def _json(value) -> bytes:
    return json.dumps(value).encode()


API_LISTING = _json({"data": [
    {"id": "a1", "url": "https://walls.test/w/a1", "path": "https://w.walls.test/full/a1.jpg",
     "dimension_x": 3840, "dimension_y": 2160, "resolution": "3840x2160",
     "created_at": "2026-09-24 10:00:00", "thumbs": {"large": "https://th.walls.test/lg/a1.jpg"}},
    {"id": "b2", "url": "https://walls.test/w/b2", "path": "https://w.walls.test/full/b2.png",
     "resolution": "1920x1080"},
    {"id": "no-image", "url": "https://walls.test/w/c3"},
], "meta": {"current_page": 1}})

WRAPPED_LISTING = _json({"kind": "Listing", "data": {"children": [
    {"kind": "t3", "data": {"id": "p1", "title": "Mountain dawn", "url": "https://img.test/p1.jpg",
                            "permalink": "https://board.test/p1", "created_utc": 1790000000}},
]}})

NESTED_MEDIA = _json({"title": "Public photos", "items": [
    {"title": "Harbour", "link": "https://photos.test/1", "media": {"m": "https://live.photos.test/1_m.jpg"},
     "published": "2026-09-23T08:00:00Z"},
]})

TOP_LEVEL_ARRAY = _json([{"name": "Aurora", "image": "https://cdn.test/render?id=9", "width": 6000, "height": 4000}])


def test_an_api_listing_yields_declared_sizes_on_the_entrys_own_image():
    document = json_image_listing(API_LISTING, "https://walls.test/api/v1/search", 30)
    assert document is not None and document.format == "json-listing"
    first, second = document.items
    assert [(c.url, c.width, c.height, c.relation) for c in first.images] == [
        ("https://w.walls.test/full/a1.jpg", 3840, 2160, "listing"),
        ("https://th.walls.test/lg/a1.jpg", None, None, "listing-variant"),
    ]
    assert first.action_url == "https://walls.test/w/a1" and first.published_at
    assert (second.images[0].width, second.images[0].height) == (1920, 1080)


def test_wrapped_nested_and_top_level_array_shapes():
    wrapped = json_image_listing(WRAPPED_LISTING, "https://board.test/r/x.json", 10)
    assert wrapped.items[0].title == "Mountain dawn"
    assert wrapped.items[0].images[0].url == "https://img.test/p1.jpg"
    assert wrapped.items[0].action_url == "https://board.test/p1"

    nested = json_image_listing(NESTED_MEDIA, "https://photos.test/feed.json", 10)
    assert nested.title == "Public photos"
    assert [(c.url, c.relation) for c in nested.items[0].images] == [
        ("https://live.photos.test/1_m.jpg", "listing-variant")]

    array = json_image_listing(TOP_LEVEL_ARRAY, "https://cdn.test/list", 10)
    # An extension-less URL still counts under an image-naming key; the header probe verifies it.
    assert (array.items[0].images[0].url, array.items[0].images[0].width) == ("https://cdn.test/render?id=9", 6000)


def test_payloads_that_are_not_listings_are_declined():
    for payload in (b'{"status": "ok", "count": 3}', b"not json", _json({"data": [{"id": 1}]})):
        assert json_image_listing(payload, "https://api.test/x", 10) is None


class _Transport:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        return FeedHttpResponse("ok", self.payload, url, content_type="application/json")


def test_feed_source_reads_a_listing_through_its_adapter_without_discovery(tmp_path: Path):
    transport = _Transport(API_LISTING)
    source = FeedSource(
        FeedSourceSpec("wallpaper:x", "https://walls.test/api/v1/search", "wallpaper_x"),
        transport=transport, cache=FeedCacheStore(tmp_path), now=lambda: 1000.0,
        document_adapter=json_image_listing,
    )
    result = source.refresh()
    assert result.status == "available"
    assert result.snapshot.document.format == "json-listing"
    assert transport.calls == ["https://walls.test/api/v1/search"]   # no discovery guesses
    # The adapted document persists like any feed (last-good, conditional refresh).
    assert FeedCacheStore(tmp_path).read("wallpaper_x").snapshot.document.items[0].images[0].width == 3840
