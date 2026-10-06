"""Artwork eviction with several live sources (the Custom 2–4 activation gate).

Each source's artwork warm evicts least-recently-used cache files after it
writes. What it must never evict is an image another source is *currently*
showing, including one that source published after this warm was submitted
(for example an older file reused from the cache). Headless: real cache files
in a temp directory, real feed owner, deterministic worker admission.
"""
from __future__ import annotations

from io import BytesIO
import os
import time
from types import SimpleNamespace

from PIL import Image

import core.feeds.artwork as artwork
from core.feeds.artwork import FeedArtworkCache
from core.feeds.config import CustomFeedConfig
from core.feeds.models import (FeedDocument, FeedHealth, FeedImageCandidate, FeedItem,
                               FeedRefreshResult, FeedSnapshot)
from widgets import feed_runtime
from widgets.feed_runtime import FeedRuntimeConfig, FeedRuntimeLease


def _picture(color: str) -> bytes:
    out = BytesIO()
    Image.new("RGB", (110, 70), color).save(out, format="PNG")
    return out.getvalue()


def _item(identity: str, url: str) -> FeedItem:
    return FeedItem(identity, identity, f"https://example.test/{identity}",
                    images=(FeedImageCandidate(url),))


def _age(path, seconds_ago: float) -> None:
    stamp = time.time() - seconds_ago
    os.utime(path, (stamp, stamp))


def test_a_cache_hit_refreshes_age_so_eviction_is_least_recently_used(tmp_path, monkeypatch):
    cache = FeedArtworkCache(tmp_path)
    old = cache.warm([_item("old", "https://cdn.example.test/old.png")],
                     fetch_bytes=lambda _u: _picture("red"), still_needed=lambda: True)
    idle = cache.warm([_item("idle", "https://cdn.example.test/idle.png")],
                      fetch_bytes=lambda _u: _picture("blue"), still_needed=lambda: True)
    _age(cache._file("https://cdn.example.test/old.png"), 300)
    _age(cache._file("https://cdn.example.test/idle.png"), 200)
    # "old" is shown again (a cache hit): it becomes the most recently used.
    cache.warm([_item("old", "https://cdn.example.test/old.png")],
               fetch_bytes=lambda _u: _picture("red"), still_needed=lambda: True)
    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 2)
    cache.warm([_item("new", "https://cdn.example.test/new.png")],
               fetch_bytes=lambda _u: _picture("green"), still_needed=lambda: True)
    assert cache.cached("https://cdn.example.test/old.png") == old.local_by_item["old"]
    assert cache.cached("https://cdn.example.test/idle.png") == ""
    del idle


def test_protection_is_read_when_the_warm_evicts_not_when_it_was_submitted(tmp_path, monkeypatch):
    cache = FeedArtworkCache(tmp_path)
    reused = cache.warm([_item("x", "https://cdn.example.test/x.png")],
                        fetch_bytes=lambda _u: _picture("red"), still_needed=lambda: True)
    _age(cache._file("https://cdn.example.test/x.png"), 600)
    published: set[str] = set()

    def fetch(_url: str) -> bytes:
        # While this warm downloads, another source publishes the older cached x.
        published.update(reused.local_by_item.values())
        return _picture("green")

    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 1)
    cache.warm([_item("a", "https://cdn.example.test/a.png")], fetch_bytes=fetch,
               still_needed=lambda: True, protected_sources=lambda: frozenset(published))
    assert cache.cached("https://cdn.example.test/x.png") == reused.local_by_item["x"]


class _DeferredManager:
    def __init__(self):
        self.tasks = []

    def submit_io_task(self, work, *, callback, **_kwargs):
        self.tasks.append((work, callback))

    def finish(self, work, callback):
        try:
            callback(SimpleNamespace(success=True, result=work()))
        except Exception as exc:
            callback(SimpleNamespace(success=False, result=None, error=exc))

    def take(self):
        return self.tasks.pop(0)


class _Consumer:
    """The runtime holds consumers weakly, like retained presentation models."""

    _runtime_generation = 91

    def __init__(self):
        self.accepted = []

    def is_feed_consumer_alive(self):
        return True

    def on_feed_runtime_result(self, result, *, from_cache):
        self.accepted.append(result)


def _lease(manager, slot: str, url: str):
    config = CustomFeedConfig.from_mapping(slot, {
        "enabled": True, "name": slot, "feed_url": url, "refresh_minutes": 15,
        "show_images": True, "view_mode": "grid",
    })
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(config, 15), generation=91, manager=manager,
        ui_dispatch=lambda fn: fn(), schedule=lambda _ms, _fn: (lambda: None), task_priority=0)
    consumer = _Consumer()
    lease.attach_consumer(consumer)
    return lease, consumer


class _Source:
    def __init__(self, items):
        now = time.time()
        self.result = FeedRefreshResult(
            "available", FeedSnapshot(FeedDocument("Feed", "https://example.test/", "rss20", items), now),
            FeedHealth(last_checked_at=now, last_success_at=now))

    def load_cached(self):
        return self.result

    def refresh(self, *, force=False):
        return self.result


def _wire(monkeypatch, tmp_path, sources):
    import core.feeds.artwork_transport as transport
    import core.settings.storage_paths as storage_paths

    monkeypatch.setattr(storage_paths, "get_feed_cache_dir", lambda _profile=None: tmp_path)
    colors = iter(["green", "yellow", "purple", "orange", "cyan", "white"])
    monkeypatch.setattr(transport, "fetch_artwork_bytes", lambda _url, **_k: _picture(next(colors)))

    def source_for(_owner, state):
        state.source = sources[state.spec.url]
        return state.source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)


def setup_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def teardown_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def test_serialized_source_artwork_preserves_already_published_peer_artwork(tmp_path, monkeypatch):
    """Published peer art remains protected while the next source warms.

    Remote FEEDS bundles are serialized now, so the old test state where A and
    B had overlapping artwork workers is intentionally impossible. The separate
    cache-level test above still proves protection is read at eviction time;
    this integration bar proves that published peer artwork survives the next
    serialized source bundle.
    """
    monkeypatch.setattr(feed_runtime, "_REMOTE_SOURCE_STAGGER_S", 0.0)
    cache = FeedArtworkCache(tmp_path / "artwork")
    seeded = cache.warm([_item("x", "https://cdn.example.test/x.png")],
                        fetch_bytes=lambda _u: _picture("red"), still_needed=lambda: True)
    _age(cache._file("https://cdn.example.test/x.png"), 900)
    sources = {
        "https://a.example.test/rss": _Source((_item("a", "https://cdn.example.test/a.png"),)),
        "https://b.example.test/rss": _Source((_item("x", "https://cdn.example.test/x.png"),)),
    }
    _wire(monkeypatch, tmp_path, sources)
    manager = _DeferredManager()
    lease_b, shown_b = _lease(manager, "feeds_custom_2", "https://b.example.test/rss")
    lease_a, _shown_a = _lease(manager, "feeds_custom_1", "https://a.example.test/rss")
    assert lease_b.start() and lease_a.start()

    # Cache reads may overlap, but only one remote/artwork bundle may own the
    # family lane. Finish B's cache first and retain A's cache callback.
    b_cache = manager.take()
    a_cache = manager.take()
    manager.finish(*b_cache)
    b_artwork = manager.take()
    manager.finish(*b_artwork)
    assert dict(shown_b.accepted[-1].local_artwork_by_item)["x"] == seeded.local_by_item["x"]

    # A now becomes eligible; its warm must see B's published x in the owner's
    # current protected set and preserve it while writing a.png.
    manager.finish(*a_cache)
    a_artwork = manager.take()
    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 1)
    manager.finish(*a_artwork)
    assert cache.cached("https://cdn.example.test/x.png") == seeded.local_by_item["x"]
    assert cache.cached("https://cdn.example.test/a.png")

    lease_a.retire()
    lease_b.retire()


def test_a_retired_source_during_its_artwork_job_evicts_nothing(tmp_path, monkeypatch):
    cache = FeedArtworkCache(tmp_path / "artwork")
    seeded = cache.warm([_item("x", "https://cdn.example.test/x.png")],
                        fetch_bytes=lambda _u: _picture("red"), still_needed=lambda: True)
    sources = {"https://a.example.test/rss": _Source((_item("a", "https://cdn.example.test/a.png"),))}
    _wire(monkeypatch, tmp_path, sources)
    manager = _DeferredManager()
    lease_a, shown_a = _lease(manager, "feeds_custom_1", "https://a.example.test/rss")
    assert lease_a.start()
    manager.finish(*manager.take())
    a_artwork = manager.take()
    monkeypatch.setattr(artwork, "CACHE_MAX_FILES", 0)
    lease_a.retire()                          # retired while its image job is queued/in flight
    manager.finish(*a_artwork)
    assert cache.cached("https://cdn.example.test/x.png") == seeded.local_by_item["x"]
    assert cache.cached("https://cdn.example.test/a.png") == ""
    assert all(not result.local_artwork_by_item for result in shown_a.accepted)
