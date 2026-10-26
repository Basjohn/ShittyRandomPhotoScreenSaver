"""Pool admission uses the existing source/cache/pass owners, never a scheduler."""
from dataclasses import replace
import json
from urllib.parse import parse_qs, urlparse

import pytest

from sources.rss.pools import (
    DISCOVERY_ORDERS, WALLPAPER_POOLS, WallpaperPoolRotation,
    WallpaperPoolSelection, migrate_legacy_curated_sources, pool_endpoint,
)


@pytest.mark.parametrize("order", [key for key, _ in DISCOVERY_ORDERS])
def test_wallhaven_maps_global_order_and_never_combines_themes(order):
    pool = WALLPAPER_POOLS[0]
    endpoint = pool_endpoint(pool.pool_id, order, turn=4, seed="abc123")
    params = parse_qs(urlparse(endpoint.url).query)
    assert params["q"] == [pool.query]
    assert params["purity"] == ["100"]
    assert params["page"] == ["2"]
    if order == "random":
        assert params["sorting"] == ["random"] and params["seed"] == ["abc123"]
    elif order in {"latest", "popular"}:
        assert params["sorting"] == [{"latest": "date_added", "popular": "favorites"}[order]]
        assert "seed" not in params and "topRange" not in params
    else:
        assert params["sorting"] == ["toplist"]
        assert params["topRange"] == [{"today": "1d", "week": "1w", "month": "1M", "year": "1y"}[order]]


def test_rotation_bounds_documents_before_fetch_and_is_fair_to_custom_sources():
    custom = [f"https://custom.test/{n}" for n in range(5)]
    selected = tuple(pool.pool_id for pool in WALLPAPER_POOLS)
    rotation = WallpaperPoolRotation(custom, WallpaperPoolSelection(True, selected, "random"), seed="a")
    seen = set()
    for _ in range(len(custom) + len(selected)):
        endpoints = rotation.next_endpoints()
        assert sum(2 if e.pool_id == "nasa.space" else 1 for e in endpoints) <= 2
        assert len({e.url for e in endpoints}) == len(endpoints)
        seen.update(e.pool_id or e.url for e in endpoints)
    assert set(custom) | set(selected) == seen
    assert WallpaperPoolRotation([], WallpaperPoolSelection(False, selected, "latest"), seed="a").next_endpoints() == ()


@pytest.mark.parametrize("order", [key for key, _ in DISCOVERY_ORDERS])
def test_native_order_providers_never_invent_ranking(order):
    for key in ("nasa.space", "bing.daily", "safebooru.general", "yandere.safe"):
        assert pool_endpoint(key, order).url == pool_endpoint(key, "latest").url
    tags = parse_qs(urlparse(pool_endpoint("konachan.safe", order).url).query)["tags"][0]
    assert "rating:safe" in tags
    assert ("order:score" in tags) == (order == "popular")


def test_nasa_space_rotates_four_subject_groups_without_bursting_solar_bodies():
    rotation = WallpaperPoolRotation([], WallpaperPoolSelection(True, ("nasa.space",), "latest"), seed="a")
    subjects = [parse_qs(urlparse(rotation.next_endpoints()[0].url).query)["title"][0] for _ in range(32)]
    assert all(subjects[index::4] == [subject] * 8 for index, subject in enumerate(("Galaxy", "Mars", "Sun")))
    assert len(set(subjects[3::4])) == 8


def test_legacy_migration_promotes_only_exact_curated_urls_preserving_custom_mixtures():
    from sources.rss.constants import LEGACY_CURATED_RSS_FEEDS
    feeds = list(LEGACY_CURATED_RSS_FEEDS.values())
    original = {"rss_feeds": feeds, "folders": ["X:/authored"], "local_ratio": 37}
    migrated = migrate_legacy_curated_sources(original)
    assert migrated["rss_feeds"] == [] and migrated["wallpaper_pools"]["enabled"]
    assert migrated["folders"] == original["folders"] and migrated["local_ratio"] == 37
    assert original["rss_feeds"] == feeds
    assert migrate_legacy_curated_sources(migrated) is None
    assert {"nasa.space", "bing.daily"} <= set(migrated["wallpaper_pools"]["selected"])
    custom = ["https://custom.test/feed", feeds[0] + "?authored=1"]
    mixed = migrate_legacy_curated_sources({"rss_feeds": [custom[0], feeds[0], custom[1]]})
    assert mixed["rss_feeds"] == custom
    assert mixed["wallpaper_pools"]["selected"] == ["nasa.space"]
    assert migrate_legacy_curated_sources({"rss_feeds": custom}) is None


@pytest.mark.parametrize("host,field,rating", [("wallhaven.cc", "purity", "sfw"), ("konachan.net", "rating", "s"), ("safebooru.org", "rating", "general"), ("yande.re", "rating", "s")])
def test_selected_pool_fails_closed_on_rating_even_if_query_ignored(host, field, rating):
    from sources.rss.json_listing import safe_pool_image_listing
    rows = [{"id": n, "file_url": f"https://cdn.test/{n}.jpg", field: value} for n, value in enumerate((rating, "q", "e", None))]
    provider = {"wallhaven.cc": "wallhaven", "konachan.net": "konachan", "safebooru.org": "safebooru", "yande.re": "yandere"}[host]
    document = safe_pool_image_listing(json.dumps(rows).encode(), "https://redirected.test/listing", 50, provider=provider)
    assert len(document.items) == 1
    assert document.items[0].images[0].url == "https://cdn.test/0.jpg"


def test_nasa_search_admits_only_images_and_manifest_uses_returned_original():
    from sources.rss.nasa_listing import nasa_image_listing
    def row(nasa_id, title, media_type="image"):
        return {"data": [{"nasa_id": nasa_id, "title": title, "media_type": media_type}]}
    data = {"collection": {"items": [row("test/id", "Mars"), row("b", "Mars Animation"), row("c", "Mars", "video")]}}
    document = nasa_image_listing(json.dumps(data).encode(), "https://images-api.nasa.gov/search?q=mars", 50)
    assert len(document.items) == 1
    assert document.items[0].action_url == "https://images-api.nasa.gov/asset/test%2Fid"
    assert document.items[0].images == ()  # previews never become wallpaper originals
    data = {"collection": {"items": [{"href": url} for url in ["https://images-assets.nasa.gov/image/id/id~thumb.jpg", "https://images-assets.nasa.gov/image/id/id~orig.jpg", "https://images-assets.nasa.gov/image/id/metadata.json"]]}}
    document = nasa_image_listing(json.dumps(data).encode(), "https://images-api.nasa.gov/asset/id", 50)
    assert len(document.items) == 1
    assert document.items[0].images[0].url.endswith("id~orig.jpg")


def test_pool_pagination_reuses_source_health_not_a_new_cache_owner(tmp_path):
    from sources.rss.coordinator import RSSCoordinator
    coordinator = RSSCoordinator(feed_urls=[], cache_dir=tmp_path / "rss")
    first = pool_endpoint("wallhaven.nature", "random", seed="fixed")
    next_page = pool_endpoint("wallhaven.nature", "random", turn=1, seed="fixed")
    source = coordinator._source(first.url, pool_endpoint=first)
    assert coordinator._source(next_page.url, pool_endpoint=next_page) is source
    assert source.spec.url == next_page.url
    assert len(coordinator._sources) == 1


@pytest.mark.parametrize("header,expected", [("3600", 4600), ("Thu, 01 Jan 1970 02:00:00 GMT", 7200), ("nonsense", 1060)])
def test_retry_after_remains_persisted_source_backoff(tmp_path, header, expected):
    from core.feeds.cache import FeedCacheStore
    from core.feeds.models import FeedSourceSpec
    from core.feeds.source import FeedSource
    from core.feeds.transport import FeedTransportError
    class Transport:
        calls = 0
        def fetch(self, *args, **kwargs):
            self.calls += 1
            raise FeedTransportError("HTTP 429", status_code=429, retry_after=header)
    transport = Transport()
    source = FeedSource(FeedSourceSpec("test", "https://test.invalid/feed", "test"), transport=transport,
                        cache=FeedCacheStore(tmp_path), now=lambda: 1000)
    first = source.refresh()
    assert first.health.backoff_until == expected
    assert source.refresh().health == first.health and transport.calls == 1


def test_nasa_pass_fetches_search_and_one_manifest_only(tmp_path, monkeypatch):
    from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem
    from sources.rss.coordinator import RSSCoordinator
    selection = WallpaperPoolSelection(True, ("nasa.space",), "latest")
    coordinator = RSSCoordinator(feed_urls=[], cache_dir=tmp_path, pool_selection=selection)
    calls = []
    def document(url, **kwargs):
        calls.append(url)
        if "/search?" in url:
            return FeedDocument("search", url, "nasa-search", tuple(FeedItem(str(i), str(i), f"https://images-api.nasa.gov/asset/{i}") for i in range(20)))
        return FeedDocument("asset", url, "nasa-asset", (FeedItem("one", "one", url, images=(FeedImageCandidate("https://cdn.test/too-small.jpg", width=10, height=10),)),))
    monkeypatch.setattr(coordinator, "_document", document)
    assert coordinator.load_sync() == []
    assert len(calls) == 2 and sum("/asset/" in url for url in calls) == 1


@pytest.mark.parametrize("payload", [
    b'<html><head><link rel="alternate" type="application/rss+xml" href="https://other.test/feed"/></head></html>',
    b'<rss version="2.0"><channel><title>Bypass</title><item><title>No rating</title><enclosure url="https://cdn.test/original.jpg" type="image/jpeg"/></item></channel></rss>',
    b'{"version":"https://jsonfeed.org/version/1.1","title":"Bypass","items":[{"id":"1","image":"https://cdn.test/original.jpg"}]}',
])
def test_pool_source_never_discovers_or_accepts_generic_feed_bypassing_ratings(tmp_path, payload):
    from core.feeds.transport import FeedHttpResponse
    from sources.rss.coordinator import RSSCoordinator
    coordinator = RSSCoordinator(feed_urls=[], cache_dir=tmp_path)
    endpoint = pool_endpoint("konachan.safe", "latest")
    source = coordinator._source(endpoint.url, pool_endpoint=endpoint)
    class Transport:
        calls = []
        def fetch(self, url, **kwargs):
            self.calls.append(url)
            return FeedHttpResponse("ok", payload, url)
    transport = Transport()
    source.transport = transport
    assert source.refresh().snapshot is None
    assert transport.calls == [endpoint.url]


def test_new_provider_cannot_fall_through_to_nasa(monkeypatch):
    import sources.rss.pools as module
    pool = replace(WALLPAPER_POOLS[0], provider="unimplemented")
    monkeypatch.setitem(module._BY_ID, pool.pool_id, pool)
    with pytest.raises(ValueError, match="Unsupported wallpaper pool provider"):
        pool_endpoint(pool.pool_id, "latest")


def test_rate_limited_pool_fences_next_same_host_pool_without_new_transport(tmp_path, monkeypatch):
    import sources.rss.coordinator as module
    from core.feeds.transport import FeedTransportError
    coordinator = module.RSSCoordinator(feed_urls=[], cache_dir=tmp_path)
    first = pool_endpoint("wallhaven.nature", "latest")
    second = pool_endpoint("wallhaven.space", "latest")
    calls = []
    class Transport:
        def fetch(self, url, **kwargs):
            calls.append(url)
            raise FeedTransportError("HTTP 429", status_code=429, retry_after="3600")
    for endpoint in (first, second):
        source = coordinator._source(endpoint.url, pool_endpoint=endpoint)
        source.now = lambda: 1000
        source.transport = Transport()
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    assert coordinator._document(first.url, pool_endpoint=first) is None
    assert coordinator._document(second.url, pool_endpoint=second) is None
    assert calls == [first.url]


def test_pool_page_change_preserves_backoff_and_does_not_send_other_pages_etag(tmp_path):
    from core.feeds.transport import FeedHttpResponse
    from sources.rss.coordinator import RSSCoordinator
    coordinator = RSSCoordinator(feed_urls=[], cache_dir=tmp_path)
    first = pool_endpoint("wallhaven.nature", "latest")
    second = pool_endpoint("wallhaven.nature", "latest", turn=1)
    source = coordinator._source(first.url, pool_endpoint=first)
    calls = []
    class Transport:
        def fetch(self, url, **kwargs):
            calls.append((url, kwargs))
            payload = json.dumps({"data": [{"id": len(calls), "path": "https://cdn.test/original.jpg", "purity": "sfw"}]}).encode()
            return FeedHttpResponse("ok", payload, url, etag="test-etag")
    source.transport = Transport()
    assert source.refresh().snapshot is not None
    assert coordinator._source(second.url, pool_endpoint=second) is source
    assert source.refresh().snapshot is not None
    assert calls[1][1]["etag"] == ""
