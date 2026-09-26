"""F3 event-admitted integration: source first, one shared bounded artwork job.

No Qt, network, independent image worker, timer or real user cache is needed.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import time

from PIL import Image

from core.feeds.config import CustomFeedConfig
from core.feeds.models import (
    FeedDocument, FeedHealth, FeedImageCandidate, FeedItem,
    FeedRefreshResult, FeedSnapshot,
)
from core.feeds.projection import project_feed
from core.settings.default_contract import require_canonical_default
from core.settings.ui_bucket_state import normalize_widget_bucket_states
from widgets import feed_runtime
from widgets.feed_runtime import FeedRuntimeConfig, FeedRuntimeLease


class Manager:
    def __init__(self):
        self.submissions = 0

    def submit_io_task(self, work, *, callback, **_kwargs):
        self.submissions += 1
        try:
            callback(SimpleNamespace(success=True, result=work()))
        except Exception as error:
            callback(SimpleNamespace(success=False, error=error, result=None))


class Source:
    def __init__(self, result):
        self.result = result
        self.reads = 0
        self.fetches = 0

    def load_cached(self):
        self.reads += 1
        return self.result

    def refresh(self, *, force=False):
        self.fetches += 1
        return self.result


class Consumer:
    def __init__(self):
        self.accepted = []
        self.alive = True

    def is_feed_consumer_alive(self):
        return self.alive

    def on_feed_runtime_result(self, result, *, from_cache):
        self.accepted.append((result, from_cache))


def png() -> bytes:
    content = BytesIO()
    Image.new("RGB", (128, 80), "white").save(content, format="PNG")
    return content.getvalue()


def content_result():
    now = time.time()
    return FeedRefreshResult(
        "available",
        FeedSnapshot(FeedDocument("Photos", "https://example.test", "rss20", (
            FeedItem("1", "First", "https://example.test/one", images=(
                FeedImageCandidate("https://cdn.example.test/1.jpg", relation="media"),)),
            FeedItem("2", "Second", "https://example.test/two", images=(
                FeedImageCandidate("https://cdn.example.test/2.jpg", relation="media"),)),
        )), fetched_at=now),
        FeedHealth(last_success_at=now, last_checked_at=now),
    )


def setup_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def teardown_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def test_settings_bucket_schema_contains_every_live_feed_builder_identity():
    from core.settings.default_settings import DEFAULT_SETTINGS
    canonical = DEFAULT_SETTINGS["ui"]["widget_bucket_states"]
    for bucket in ("custom_1_source", "custom_1_content", "custom_1_layout", "custom_1_appearance"):
        assert canonical[f"feeds:{bucket}"] is False
    normalized = normalize_widget_bucket_states(canonical, {"feeds:custom_1_source": True})
    assert normalized["feeds:custom_1_source"]
    assert not any(normalized[f"feeds:{name}"] for name in (
        "custom_1_content", "custom_1_layout", "custom_1_appearance"))
    assert require_canonical_default("widgets.feeds_custom_1.show_images") is True


def test_cached_news_paints_before_one_source_owned_artwork_completion(tmp_path, monkeypatch):
    """Cache-first presentation stays responsive, no second feed request or timer."""
    from core.feeds import artwork_transport
    from core.settings import storage_paths

    monkeypatch.setattr(storage_paths, "get_feed_cache_dir", lambda profile=None: tmp_path)
    requested = []
    def fetch(url, **_kwargs):
        requested.append(url)
        out = BytesIO()
        color = "red" if url.endswith("/1.jpg") else "blue"
        Image.new("RGB", (32, 24), color).save(out, format="PNG")
        return out.getvalue()
    monkeypatch.setattr(artwork_transport, "fetch_artwork_bytes", fetch)
    source = Source(content_result())
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", lambda owner, state: source)
    manager, consumer = Manager(), Consumer()
    deadlines = []
    def schedule(delay, callback):
        deadlines.append((delay, callback))
        return lambda: None
    config = CustomFeedConfig.from_mapping("feeds_custom_1", {
        "enabled": True, "name": "Photos", "feed_url": "https://example.test/feed.xml",
        "view_mode": "grid", "item_limit": 3, "show_images": True,
    })
    lease = FeedRuntimeLease(config=FeedRuntimeConfig.from_custom(config, 15),
                             generation=42, manager=manager, ui_dispatch=lambda callback: callback(),
                             schedule=schedule,
                             task_priority=0)
    lease.attach_consumer(consumer)
    assert lease.start()
    assert manager.submissions == 2  # cache read + event-admitted artwork, no extra feed GET
    assert deadlines and all(delay >= 300000 for delay, _ in deadlines)  # existing feed deadline only
    assert source.reads == 1 and source.fetches == 0
    assert len(consumer.accepted) == 2
    first, _ = consumer.accepted[0]
    final, _ = consumer.accepted[1]
    assert first.snapshot == final.snapshot
    assert first.local_artwork_by_item == ()
    assert len(final.local_artwork_by_item) == 2
    assert len(requested) == 2
    shown = project_feed(final.snapshot, view_mode="grid", item_limit=3,
                         local_artwork_by_item=dict(final.local_artwork_by_item))
    assert shown.image_mode == "complete"
    assert all(row.image_source.startswith("file:") for row in shown.rows)
    assert len(tuple((tmp_path / "artwork").glob("*.png"))) == 2
    assert not any("http" in source for _, source in final.local_artwork_by_item)
    lease.stop()
    lease.retire()

    # A later activation reuses durable art with no extra image requests.
    second = Consumer()
    later = FeedRuntimeLease(config=FeedRuntimeConfig.from_custom(config, 15),
                             generation=43, manager=Manager(),
                             ui_dispatch=lambda callback: callback(),
                             schedule=lambda _delay, _callback: (lambda: None),
                             task_priority=0)
    later.attach_consumer(second)
    assert later.start()
    assert len(second.accepted) == 2
    assert second.accepted[-1][0].local_artwork_by_item == final.local_artwork_by_item
    assert len(requested) == 2
    later.retire()


def test_image_disabled_source_has_no_artwork_submissions(monkeypatch):
    source = Source(content_result())
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", lambda owner, state: source)
    manager = Manager()
    config = CustomFeedConfig.from_mapping("feeds_custom_1", {
        "enabled": True, "feed_url": "https://example.test/feed.xml",
        "show_images": False, "view_mode": "grid",
    })
    lease = FeedRuntimeLease(config=FeedRuntimeConfig.from_custom(config, 15),
                             generation=44, manager=manager,
                             ui_dispatch=lambda callback: callback(),
                             schedule=lambda _delay, _callback: (lambda: None),
                             task_priority=0)
    consumer = Consumer()
    lease.attach_consumer(consumer)
    assert lease.start()
    assert manager.submissions == 1 and source.reads == 1
    lease.retire()


def test_feed_article_rows_have_event_driven_hover_and_pointer_affordance():
    qml = (Path(__file__).resolve().parents[1] / "rendering/quick/qml/FeedPresentation.qml").read_text("utf-8")
    assert 'objectName: "feedListHoverFrame" + index' in qml
    assert 'id: listHover' in qml and 'cursorShape: Qt.PointingHandCursor' in qml
    assert 'id: gridHover' in qml
    assert qml.count('cursorShape: Qt.PointingHandCursor') >= 3  # refresh + list + grid
    assert 'enabled: parent.canActivate' in qml


def test_artwork_warms_only_rows_an_active_card_can_show(tmp_path, monkeypatch):
    """Stories past every card's item limit never show art, so none is fetched,
    published or protected from eviction. A card with a larger limit joining an
    already-warmed source gets exactly one more bounded warm."""
    from core.feeds import artwork_transport
    from core.settings import storage_paths

    monkeypatch.setattr(storage_paths, "get_feed_cache_dir", lambda profile=None: tmp_path)
    requested = []

    def fetch(url, **_kwargs):
        requested.append(url)
        out = BytesIO()
        Image.new("RGB", (32, 24), (len(requested) * 30 % 255, 90, 160)).save(out, format="PNG")
        return out.getvalue()

    monkeypatch.setattr(artwork_transport, "fetch_artwork_bytes", fetch)
    now = time.time()
    items = tuple(
        FeedItem(str(i), f"Story {i}", f"https://example.test/{i}", images=(
            FeedImageCandidate(f"https://cdn.example.test/{i}.jpg", relation="media"),))
        for i in range(1, 7)
    )
    result = FeedRefreshResult(
        "available",
        FeedSnapshot(FeedDocument("Six", "https://example.test", "rss20", items), fetched_at=now),
        FeedHealth(last_success_at=now, last_checked_at=now),
    )
    source = Source(result)
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", lambda owner, state: source)

    def lease_for(widget_id, item_limit):
        config = CustomFeedConfig.from_mapping(widget_id, {
            "enabled": True, "feed_url": "https://example.test/feed.xml",
            "view_mode": "list", "item_limit": item_limit, "show_images": True,
        })
        lease = FeedRuntimeLease(config=FeedRuntimeConfig.from_custom(config, 15),
                                 generation=45, manager=Manager(),
                                 ui_dispatch=lambda callback: callback(),
                                 schedule=lambda _delay, _callback: (lambda: None),
                                 task_priority=0)
        consumer = Consumer()
        lease.attach_consumer(consumer)
        return lease, consumer

    small, small_consumer = lease_for("feeds_custom_1", 3)
    assert small.start()
    warmed = dict(small_consumer.accepted[-1][0].local_artwork_by_item)
    assert set(warmed) == {"1", "2", "3"}
    assert sorted(requested) == [f"https://cdn.example.test/{i}.jpg" for i in (1, 2, 3)]

    # Same endpoint, larger limit: one more warm, new requests only for 4 and 5.
    large, large_consumer = lease_for("feeds_custom_2", 5)
    assert large.start()
    widened = dict(large_consumer.accepted[-1][0].local_artwork_by_item)
    assert set(widened) == {"1", "2", "3", "4", "5"}
    assert len(requested) == 5
    assert "https://cdn.example.test/6.jpg" not in requested
    small.retire()
    large.retire()
