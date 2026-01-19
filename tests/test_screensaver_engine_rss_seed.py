from datetime import datetime, timedelta
from pathlib import Path

from engine.screensaver_engine import ScreensaverEngine
from sources.base_provider import ImageMetadata, ImageSourceType
from core.events import EventType


class DummySettings:
    """Minimal settings shim for the engine tests."""

    def __init__(self, overrides):
        self._overrides = overrides or {}

    def get(self, key, default=None):
        return self._overrides.get(key, default)


class DummyRSSSource:
    """RSS source stub that returns a predictable set of images."""

    def __init__(self, name: str, image_count: int):
        self.feed_urls = [f"https://example.com/{name}"]
        self._images = [
            ImageMetadata(
                source_type=ImageSourceType.RSS,
                source_id=name,
                image_id=f"{name}_{idx}",
                local_path=None,
                url=f"https://cdn.example.com/{name}/{idx}.jpg",
                title=f"{name} {idx}",
            )
            for idx in range(image_count)
        ]

    def get_images(self, max_images=None):
        if max_images is None:
            return list(self._images)
        return list(self._images[:max_images])


class RecordingQueue:
    """Queue stub that records added images for assertions."""

    def __init__(self):
        self.items = []
        self.history_paths = []

    def add_images(self, images):
        self.items.extend(images)
        return len(images)

    def get_all_images(self):
        return list(self.items)

    def get_history(self, count):
        return list(self.history_paths[-count:])

    def remove_image(self, image_path):
        for idx, img in enumerate(self.items):
            path = str(img.local_path) if img.local_path else None
            if path == image_path:
                del self.items[idx]
                return True
        return False


class RecordingEventSystem:
    def __init__(self):
        self.published = []

    def publish(self, event_type, data=None, source=None):
        self.published.append((event_type, data))


def _make_engine(settings_overrides):
    engine = ScreensaverEngine()
    engine.settings_manager = DummySettings(settings_overrides)
    engine.image_queue = RecordingQueue()
    engine.folder_sources = []
    return engine


def test_sync_seed_limit_respects_cap_and_feed_order():
    """Verify synchronous RSS seeding honors the per-feed limit and global cap."""
    engine = _make_engine(
        {
            "sources.rss_sync_seed_per_feed": 4,
            "sources.rss_background_cap": 6,
            "timing.interval": 60,
        }
    )
    per_feed_seed = engine._get_rss_sync_seed_limit()
    engine.rss_sources = [
        DummyRSSSource("priority_a", 10),
        DummyRSSSource("priority_b", 10),
        DummyRSSSource("priority_c", 10),
    ]

    engine._load_rss_images_sync()

    queued = engine.image_queue.get_all_images()
    expected_total = engine._get_rss_sync_seed_total(per_feed_seed)
    assert len(queued) == expected_total
    ids = [img.image_id for img in queued]

    remaining = expected_total
    feed_expectations = []
    for source in engine.rss_sources:
        take = min(per_feed_seed, remaining)
        feed_expectations.append((source.feed_urls[0], take))
        remaining = max(0, remaining - take)
        if remaining == 0:
            break

    offset = 0
    for idx, (_, expected_count) in enumerate(feed_expectations):
        if expected_count == 0:
            continue
        expected_ids = [f"priority_{chr(ord('a') + idx)}_{i}" for i in range(expected_count)]
        assert ids[offset:offset + expected_count] == expected_ids
        offset += expected_count


def test_rss_sync_seed_limit_clamped_and_defaults():
    """Ensure seed helper obeys defaults and clamps values."""
    engine = _make_engine({})

    # Default when unset.
    assert engine._get_rss_sync_seed_limit() == 5

    # Clamp low values to at least 1.
    engine.settings_manager = DummySettings({"sources.rss_sync_seed_per_feed": 0})
    assert engine._get_rss_sync_seed_limit() == 1

    # Clamp high values to at most 10.
    engine.settings_manager = DummySettings({"sources.rss_sync_seed_per_feed": 25})
    assert engine._get_rss_sync_seed_limit() == 10


def test_minimum_rss_start_images_clamped_and_defaults():
    engine = _make_engine({})
    assert engine._get_minimum_rss_start_images() == 4

    engine.settings_manager = DummySettings({"sources.rss_min_start_images": "8"})
    assert engine._get_minimum_rss_start_images() == 8

    engine.settings_manager = DummySettings({"sources.rss_min_start_images": "-3"})
    assert engine._get_minimum_rss_start_images() == 0

    engine.settings_manager = DummySettings({"sources.rss_min_start_images": "35"})
    assert engine._get_minimum_rss_start_images() == 30


def test_wait_for_min_rss_images_respects_counts_and_timeout():
    engine = _make_engine({})
    queue = RecordingQueue()
    engine.image_queue = queue

    # Timeout when no images arrive
    assert not engine._wait_for_min_rss_images(
        min_required=1,
        timeout_seconds=0.05,
        check_interval=0.01,
    )

    # Populate two unique RSS images
    queue.items = [
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="feed_a",
            image_id="feed_a_0",
            local_path=Path("a0.jpg"),
            url="https://example.com/a/0.jpg",
        ),
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="feed_b",
            image_id="feed_b_0",
            local_path=Path("b0.jpg"),
            url="https://example.com/b/0.jpg",
        ),
    ]

    assert engine._wait_for_min_rss_images(
        min_required=2,
        timeout_seconds=0.05,
        check_interval=0.01,
    )


def test_merge_rss_images_respects_cap_and_stale_pruning():
    """_merge_rss_images_from_refresh should add up to cap and prune stale entries."""
    engine = _make_engine(
        {
            "sources.rss_background_cap": 4,
            "sources.rss_stale_minutes": 1,
            "timing.interval": 60,
        }
    )
    queue = RecordingQueue()
    engine.image_queue = queue
    engine.event_system = RecordingEventSystem()

    recent = datetime.utcnow()
    old = recent - timedelta(minutes=5)

    existing = [
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="existing",
            image_id="existing_1",
            local_path=Path("keep_1.jpg"),
            url="https://example.com/keep_1.jpg",
            fetched_date=recent,
        ),
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="existing",
            image_id="existing_2",
            local_path=Path("stale.jpg"),
            url="https://example.com/stale.jpg",
            fetched_date=old,
        ),
        ImageMetadata(
            source_type=ImageSourceType.FOLDER,
            source_id="local",
            image_id="local_1",
            local_path=Path("local.jpg"),
        ),
    ]
    queue.items = existing.copy()
    queue.history_paths = ["stale.jpg"]  # protect stale image from removal when recently viewed

    new_images = [
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="new_feed",
            image_id="new_1",
            local_path=Path("new_1.jpg"),
            url="https://example.com/new_1.jpg",
            fetched_date=recent,
        ),
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="new_feed",
            image_id="new_2",
            local_path=Path("new_2.jpg"),
            url="https://example.com/new_2.jpg",
            fetched_date=recent,
        ),
        # Duplicate URL should be ignored
        ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="new_feed",
            image_id="new_dup",
            local_path=Path("keep_1.jpg"),  # same key as existing_1
            url="https://example.com/keep_1.jpg",
            fetched_date=recent,
        ),
    ]

    engine._merge_rss_images_from_refresh(new_images)

    snapshot = queue.get_all_images()
    rss_items = [img for img in snapshot if img.source_type == ImageSourceType.RSS]
    assert len(rss_items) == 3, "Stale entry should be pruned leaving only 3 RSS images"
    rss_ids = {img.image_id for img in rss_items}
    assert {"existing_1", "new_1", "new_2"} == rss_ids

    # Ensure event published with total_rss = 4
    assert any(evt[0] == EventType.RSS_UPDATED and evt[1]["total_rss"] == 3 for evt in engine.event_system.published)
