"""Headless F3 artwork-cache guard; no Qt, network, timers or credentials."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image

from core.feeds.artwork import (
    ArtworkCancelled, CACHE_MAX_BYTES, CACHE_MAX_FILES, FeedArtworkCache,
    MAX_IMAGES_PER_WARM, safe_artwork_url,
)
from core.feeds.models import FeedImageCandidate, FeedItem


def _item(identity: str, url: str = "") -> FeedItem:
    return FeedItem(identity, identity, f"https://example.test/{identity}",
                    images=(FeedImageCandidate(url),) if url else ())


def _picture(*, size=(110, 70)) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, "white").save(out, format="PNG")
    return out.getvalue()


def test_safe_candidate_never_treats_local_network_or_credentials_as_public_image():
    assert safe_artwork_url("https://cdn.example.test/photo.png?private=redacted")
    for candidate in (
        "file:///home/user/secret.png", "https://127.0.0.1/x.png",
        "http://[::1]/x.png", "http://192.168.1.3/x.png",
        "https://user:password@cdn.example.test/x.png", "http://localhost/img.jpg",
        "https://cdn.example.test:7777/p.png", "https://cdn.example.test\\@127.0.0.1/p.png",
    ):
        assert not safe_artwork_url(candidate), candidate


def test_cross_item_shared_image_is_treated_as_feed_chrome_not_article_art(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    shared = "https://cdn.example.test/site-hero.jpg?secret=one"
    images = (_item("a", shared), _item("b", shared))
    visited = []
    outcome = cache.warm(
        images, fetch_bytes=lambda url: visited.append(url) or _picture(),
        still_needed=lambda: True,
    )
    assert outcome.attempts == outcome.newly_cached == 0
    assert outcome.local_by_item == {}
    assert visited == []
    assert not tuple(tmp_path.glob("*.png"))


def test_article_specific_candidate_beats_larger_shared_feed_hero(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    shared = "https://cdn.example.test/site-hero.jpg"
    rows = (
        FeedItem("a", "A", "https://example.test/a", images=(
            FeedImageCandidate(shared, width=1600, height=900, relation="media"),
            FeedImageCandidate("https://cdn.example.test/a.jpg", width=320, height=180, relation="content"),
        )),
        FeedItem("b", "B", "https://example.test/b", images=(
            FeedImageCandidate(shared, width=1600, height=900, relation="media"),
            FeedImageCandidate("https://cdn.example.test/b.jpg", width=320, height=180, relation="content"),
        )),
    )
    visited = []
    outcome = cache.warm(
        rows, fetch_bytes=lambda url: visited.append(url) or _picture(),
        still_needed=lambda: True,
    )
    assert outcome.attempts == outcome.newly_cached == 2
    assert visited == ["https://cdn.example.test/a.jpg", "https://cdn.example.test/b.jpg"]
    assert len(set(outcome.local_by_item.values())) == 2
    assert shared not in visited


def test_bad_or_large_content_does_not_destroy_existing_local_art_or_feed_rows(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    valid = _item("valid", "https://cdn.example.test/existing.png")
    fresh = cache.warm([valid], fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    damaged = _item("damaged", "https://cdn.example.test/damaged.png")
    huge = _item("huge", "https://cdn.example.test/huge.png")
    mixed = cache.warm([valid, damaged, huge], fetch_bytes=lambda url: b"not an image" if "damaged" in url else b"x" * (2 * 1024 * 1024 + 1),
                       still_needed=lambda: True)
    assert mixed.local_by_item == fresh.local_by_item
    assert mixed.attempts == 2 and mixed.newly_cached == 0
    assert cache.cached(valid.images[0].url) == fresh.local_by_item["valid"]


def test_corrupt_cached_image_is_replaced_by_a_valid_worker_result(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    item = _item("one", "https://cdn.example.test/one.png")
    first = cache.warm([item], fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    path = next(tmp_path.glob("*.png"))
    path.write_bytes(b"corrupted")
    assert cache.cached(item.images[0].url) == ""
    fixed = cache.warm([item], fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    assert fixed.newly_cached == 1
    assert fixed.local_by_item == first.local_by_item


def test_cancelled_job_does_not_publish_or_write_new_art(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    needed = [True]
    def fetch(_):
        needed[0] = False
        return _picture()
    with pytest.raises(ArtworkCancelled):
        cache.warm([_item("a", "https://cdn.example.test/a.png")],
                   fetch_bytes=fetch, still_needed=lambda: needed[0])
    assert not list(tmp_path.glob("*.png"))
    assert not list(tmp_path.glob(".feed-art-*"))


def test_worker_budget_and_missing_art_are_independent_of_item_validity(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    requests = []
    items = [_item(str(n), f"https://cdn.example.test/{n}.png") for n in range(MAX_IMAGES_PER_WARM + 3)]
    items.append(_item("text-only"))
    outcome = cache.warm(items, fetch_bytes=lambda url: requests.append(url) or _picture(), still_needed=lambda: True)
    assert outcome.attempts == outcome.newly_cached == MAX_IMAGES_PER_WARM
    assert len(outcome.local_by_item) == MAX_IMAGES_PER_WARM
    assert "text-only" not in outcome.local_by_item


def test_on_write_pruning_keeps_current_images_and_does_not_touch_neighbor_cache(tmp_path, monkeypatch):
    import core.feeds.artwork as artwork
    cache = FeedArtworkCache(tmp_path / "feeds" / "artwork")
    cache.directory.mkdir(parents=True)
    neighbor = tmp_path / "feeds" / "record.json"
    neighbor.write_text("last-good")
    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 1)
    a = cache.warm([_item("a", "https://cdn.example.test/a.png")], fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    b = cache.warm([_item("b", "https://cdn.example.test/b.png")], fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    assert len(tuple(cache.directory.glob("*.png"))) == 1
    assert cache.cached("https://cdn.example.test/b.png") == b.local_by_item["b"]
    assert cache.cached("https://cdn.example.test/a.png") == ""
    assert neighbor.read_text() == "last-good"
    assert CACHE_MAX_BYTES > 0 and CACHE_MAX_FILES > 0


def test_prune_respects_other_active_endpoint_images(tmp_path, monkeypatch):
    import core.feeds.artwork as artwork
    cache = FeedArtworkCache(tmp_path)
    first = cache.warm([_item("a", "https://cdn.example.test/a.png")],
                       fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 1)
    second = cache.warm([_item("b", "https://cdn.example.test/b.png")],
                        fetch_bytes=lambda _: _picture(), still_needed=lambda: True,
                        protected_sources=first.local_by_item.values())
    assert cache.cached("https://cdn.example.test/a.png") == first.local_by_item["a"]
    assert cache.cached("https://cdn.example.test/b.png") == second.local_by_item["b"]
    # A live protected generation can temporarily push the on-disk count over
    # the cap.  The first subsequent worker write without that protection reaps
    # the older unneeded entry; never delete a displayed image to obey a quota.
    third = cache.warm([_item("c", "https://cdn.example.test/c.png")],
                       fetch_bytes=lambda _: _picture(), still_needed=lambda: True)
    assert cache.cached("https://cdn.example.test/c.png") == third.local_by_item["c"]
    assert len(tuple(tmp_path.glob("*.png"))) == 1


def test_bad_preferred_source_falls_back_to_feed_advertised_thumbnail(tmp_path):
    cache = FeedArtworkCache(tmp_path)
    row = FeedItem(
        "fallback", "Fallback", "https://example.test/story",
        images=(
            FeedImageCandidate("https://cdn.example.test/big.png", width=1600, height=900, relation="media"),
            FeedImageCandidate("https://cdn.example.test/small.png", width=320, height=180, relation="thumbnail"),
        ),
    )
    attempts = []
    def fetch(url):
        attempts.append(url)
        return b"bad picture" if "big" in url else _picture()
    first = cache.warm([row], fetch_bytes=fetch, still_needed=lambda: True)
    assert first.attempts == 2 and first.newly_cached == 1
    assert attempts == [row.images[0].url, row.images[1].url]
    assert first.local_by_item["fallback"].startswith("file://")
    second = cache.warm([row], fetch_bytes=lambda _: (_ for _ in ()).throw(AssertionError("fallback fetched")),
                        still_needed=lambda: True)
    assert second.attempts == 0 and second.local_by_item == first.local_by_item


def test_artwork_batch_diagnostics_are_explicitly_opt_in(tmp_path, monkeypatch):
    """No FEEDS diagnostic record may exist without the --feeds sidecar gate."""
    from core.feeds import artwork as artwork_mod

    cache = FeedArtworkCache(tmp_path)
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(artwork_mod.logger, "info", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(artwork_mod, "is_feeds_logging_enabled", lambda: False)
    cache.warm((), fetch_bytes=lambda _url: b"", still_needed=lambda: True)
    assert calls == []

    monkeypatch.setattr(artwork_mod, "is_feeds_logging_enabled", lambda: True)
    cache.warm((), fetch_bytes=lambda _url: b"", still_needed=lambda: True)
    assert len(calls) == 1
    assert "[FEEDS][ARTWORK]" in str(calls[0][0][0])
    assert calls[0][1]["extra"]["srpss_log_families"] == ("feeds",)
