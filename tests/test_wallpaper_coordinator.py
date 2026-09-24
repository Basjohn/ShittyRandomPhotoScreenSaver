"""Wallpaper pool: acquisition by real pixels, rejection memory, session rotation.

The two network edges are stubbed (feed documents; the per-image vetted
fetch, which has its own tests); acquisition order, admission, memory,
rotation, retirement and the pool's files and index are the real code on real
files. Requirement (3840, 2160) is the operator's 2560x1440 + 3840x2160 pair.
"""
from __future__ import annotations

from io import BytesIO
import os
import time
from types import SimpleNamespace

import pytest
from PIL import Image

import sources.rss.coordinator as coordinator_module
import sources.rss.image_fetch as image_fetch
from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem
from sources.rss.cache import RSSCache, url_key
from sources.rss.coordinator import RSSCoordinator
from sources.rss.image_fetch import WallpaperFile, WallpaperRejected

REQUIRED = (3840, 2160)
FEED_A = "https://a.example.test/feed"
FEED_B = "https://b.example.test/feed"


@pytest.fixture(autouse=True)
def _fresh_process_session(monkeypatch):
    monkeypatch.setattr(coordinator_module, "_ROTATED_THIS_PROCESS", set())
    monkeypatch.setattr(coordinator_module, "_LOADED_THIS_PROCESS", set())
    monkeypatch.setattr(coordinator_module, "HOST_MIN_INTERVAL_SECONDS", 0.0)


def _png(path, size=(16, 16)) -> None:
    # Random pixels: comfortably above the pool's "under 100 bytes is corrupt" floor.
    out = BytesIO()
    Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)).save(out, format="PNG")
    path.write_bytes(out.getvalue())


class _Web:
    """``fetch_wallpaper`` stand-in: url -> real pixel size; records every fetch."""

    def __init__(self, sizes: dict[str, tuple[int, int]]):
        self.sizes = sizes
        self.calls: list[str] = []

    def fetch(self, url, directory, *, file_stem, still_needed, required, **_kwargs):
        self.calls.append(url)
        width, height = self.sizes[url]
        if not image_fetch.fills_displays(width, height, required):
            raise WallpaperRejected("too small", (width, height))
        path = directory / f"{file_stem}.png"
        _png(path)
        return WallpaperFile(path, width, height)


def _item(name, *candidates) -> FeedItem:
    return FeedItem(name, name, f"https://site.test/{name}",
                    images=tuple(FeedImageCandidate(url, width=w, height=h) for url, w, h in candidates))


def _coordinator(tmp_path, monkeypatch, documents, web, *, target=30):
    monkeypatch.setattr(image_fetch, "fetch_wallpaper", web.fetch)
    coordinator = RSSCoordinator(feed_urls=list(documents), cache_dir=tmp_path / "rss",
                                 target_total_images=target, required_size=REQUIRED)
    fetched_documents: list[str] = []

    def document(feed_url):
        fetched_documents.append(feed_url)
        return documents[feed_url]

    coordinator._document = document
    coordinator.fetched_documents = fetched_documents
    return coordinator


def _seed_pool(tmp_path, count, *, age_hours, size=REQUIRED, start=0):
    cache = RSSCache(cache_dir=tmp_path / "rss")
    cache.load_from_disk()
    for index in range(start, start + count):
        url = f"https://old.example.test/{index}.jpg"
        path = cache.cache_dir / f"{url_key(url)}.png"
        _png(path)
        cache.add(path, width=size[0], height=size[1], url=url, source="seed",
                  title=f"old {index}", fetched_at=time.time() - age_hours * 3600 - index)
    cache.save_state()


def test_round_robin_admits_only_images_that_fill_every_display(tmp_path, monkeypatch):
    documents = {
        FEED_A: FeedDocument("A", "", "rss20", (
            _item("a1", ("https://a.test/a1.jpg", 6000, 4000)),
            _item("a2", ("https://a.test/a2.jpg", 1920, 1080), ("https://a.test/a2-thumb.jpg", None, None)),
            _item("a3", ("https://a.test/a3.jpg", None, None)),
        )),
        FEED_B: FeedDocument("B", "", "json-listing", (
            _item("b1", ("https://b.test/b1.jpg", None, None)),
            _item("b2", ("https://b.test/b2.jpg", 3840, 2160)),
        )),
    }
    web = _Web({"https://a.test/a1.jpg": (6000, 4000), "https://a.test/a3.jpg": (1024, 683),
                "https://b.test/b1.jpg": (5000, 5000), "https://b.test/b2.jpg": (3840, 2160)})
    coordinator = _coordinator(tmp_path, monkeypatch, documents, web, target=4)
    coordinator.warm_cache()
    new = coordinator.load_sync()
    # Alternating feeds. a2 declares 1920x1080: it and its thumbnail are never
    # fetched (it still takes feed A's turn); a3 is fetched and refused by size.
    assert web.calls == ["https://a.test/a1.jpg", "https://b.test/b1.jpg",
                         "https://b.test/b2.jpg", "https://a.test/a3.jpg"]
    assert sorted((m.width, m.height) for m in new) == [(3840, 2160), (5000, 5000), (6000, 4000)]
    assert coordinator.cached_count == 3

    # A new session in the same pool never re-fetches the refused 1024 px image.
    monkeypatch.setattr(coordinator_module, "_ROTATED_THIS_PROCESS", set())
    documents[FEED_A] = FeedDocument("A", "", "rss20", (_item("a3", ("https://a.test/a3.jpg", None, None)),))
    second_web = _Web({})
    again = _coordinator(tmp_path, monkeypatch, documents, second_web, target=4)
    again.warm_cache()
    assert again.load_sync() == []
    assert second_web.calls == []


def test_a_full_fresh_pool_does_no_feed_or_image_work(tmp_path, monkeypatch):
    _seed_pool(tmp_path, 30, age_hours=1)
    web = _Web({})
    coordinator = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", ())}, web)
    assert coordinator.warm_cache() == 30
    assert coordinator.load_sync() == []
    assert coordinator.fetched_documents == [] and web.calls == []
    assert coordinator.refresh_single_feed(FEED_A) == []   # background top-up: nothing missing
    assert coordinator.fetched_documents == []


def _fresh_items(count, prefix="n"):
    return tuple(_item(f"{prefix}{i}", (f"https://new.test/{prefix}{i}.jpg", 4000, 3000)) for i in range(count))


def test_session_rotation_replaces_a_third_of_a_stale_pool_after_replacements_land(tmp_path, monkeypatch):
    _seed_pool(tmp_path, 30, age_hours=24 * 5)
    items = _fresh_items(15)
    web = _Web({item.images[0].url: (4000, 3000) for item in items})
    coordinator = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", items)}, web)
    coordinator.warm_cache()
    oldest = sorted(coordinator._cache.entries, key=lambda e: e.fetched_at)[:10]

    new = coordinator.load_sync()
    assert len(new) == 10 and coordinator.cached_count == 30
    retired = coordinator.take_retired_paths()
    assert sorted(retired) == sorted(str(e.path) for e in oldest)
    # Retired files stay until the next session start (they may be in history).
    assert all((tmp_path / "rss" / e.path.name).exists() for e in oldest)
    assert coordinator.take_retired_paths() == []

    # A settings rebuild in this process neither rotates again nor deletes the
    # retired files (still hidden); the next process session deletes them.
    more = _fresh_items(15, "m")
    rebuild_web = _Web({item.images[0].url: (4000, 3000) for item in more})
    rebuilt = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", more)}, rebuild_web)
    assert rebuilt.warm_cache() == 30
    assert all((tmp_path / "rss" / e.path.name).exists() for e in oldest)
    assert not ({str(m.local_path) for m in rebuilt.get_cached_images()} & set(retired))
    assert rebuilt.load_sync() == [] and rebuilt.take_retired_paths() == []
    assert rebuild_web.calls == []   # still stale, but this session already rotated

    monkeypatch.setattr(coordinator_module, "_LOADED_THIS_PROCESS", set())   # a new process
    next_session = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", ())}, _Web({}))
    assert next_session.warm_cache() == 30
    assert not any((tmp_path / "rss" / e.path.name).exists() for e in oldest)


def test_rotation_never_shrinks_the_pool_when_replacements_fail(tmp_path, monkeypatch):
    _seed_pool(tmp_path, 30, age_hours=24 * 5)
    coordinator = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", ())}, _Web({}))
    coordinator.warm_cache()
    assert coordinator.load_sync() == []
    assert coordinator.cached_count == 30 and coordinator.take_retired_paths() == []


def test_images_that_cannot_fill_the_displays_are_hidden_and_replaced(tmp_path, monkeypatch):
    _seed_pool(tmp_path, 25, age_hours=1)
    _seed_pool(tmp_path, 5, age_hours=1, size=(1920, 1080), start=100)
    items = _fresh_items(5)
    web = _Web({item.images[0].url: (4000, 3000) for item in items})
    coordinator = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", items)}, web)
    coordinator.warm_cache()
    assert len(coordinator.get_cached_images()) == 25        # hidden before any network work
    new = coordinator.load_sync()
    assert len(new) == 5 and coordinator.cached_count == 30
    assert len(coordinator.take_retired_paths()) == 5


def test_passes_never_overlap(tmp_path, monkeypatch):
    coordinator = _coordinator(tmp_path, monkeypatch, {FEED_A: FeedDocument("A", "", "rss20", _fresh_items(3))},
                               _Web({}))
    assert coordinator._pass_lock.acquire(blocking=False)
    try:
        assert coordinator.refresh_single_feed(FEED_A) == []
        assert coordinator.fetched_documents == []
    finally:
        coordinator._pass_lock.release()


def test_engine_removes_retired_pool_images_from_its_queue():
    from engine.engine_rss import drop_retired_rss_images

    removed: list[str] = []
    engine = SimpleNamespace(
        rss_coordinator=SimpleNamespace(take_retired_paths=lambda: ["C:/pool/a.png", "C:/pool/b.png"]),
        image_queue=SimpleNamespace(remove_image=lambda path: removed.append(path) or True),
    )
    assert drop_retired_rss_images(engine) == 2
    assert removed == ["C:/pool/a.png", "C:/pool/b.png"]
