from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sources.base_provider import ImageMetadata, ImageSourceType
from sources.rss.coordinator import RSSCoordinator
from sources.rss.parser import RSSParser
from engine.engine_rss import get_rss_startup_target_total


def _build_cached_image(index: int, cache_dir: Path) -> ImageMetadata:
    path = cache_dir / f"cached_{index}.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 128)
    return ImageMetadata(
        source_type=ImageSourceType.RSS,
        source_id="cached",
        image_id=f"cached_{index}",
        local_path=path,
        title=f"Cached {index}",
    )


def test_rss_parser_parses_flickr_z_timestamps_without_dateutil() -> None:
    entries = RSSParser.parse_json(
        {
            "items": [
                {
                    "title": "City Lights",
                    "published": "2026-06-19T10:59:36Z",
                    "media": {"m": "https://live.staticflickr.com/test/example_m.jpg"},
                }
            ]
        },
        "https://www.flickr.com/services/feeds/photos_public.gne?format=json&nojsoncallback=1",
        max_entries=5,
    )

    assert len(entries) == 1
    assert entries[0].image_url.endswith("_b.jpg")
    assert entries[0].created_date == datetime(2026, 6, 19, 10, 59, 36, tzinfo=timezone.utc)


def test_rss_startup_target_uses_real_runtime_caps() -> None:
    engine = SimpleNamespace(
        settings_manager=SimpleNamespace(
            get=lambda key, default=None: {
                "sources.rss_background_cap": 30,
                "sources.rss_rotating_cache_size": 20,
            }.get(key, default)
        )
    )

    assert get_rss_startup_target_total(engine) == 30


def test_rss_coordinator_skips_feed_work_when_cache_already_meets_target(tmp_path) -> None:
    coord = RSSCoordinator(
        feed_urls=[
            "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
            "https://www.nasa.gov/feeds/iotd-feed",
        ],
        cache_dir=tmp_path / "rss_cache",
        target_total_images=30,
    )
    coord._cache._images = [_build_cached_image(i, coord.cache_dir) for i in range(35)]

    calls: list[tuple[str, int]] = []
    coord._process_single_feed = lambda feed_url, max_images, existing_paths: calls.append((feed_url, max_images)) or []  # type: ignore[method-assign]

    result = coord.load_sync()

    assert result == []
    assert calls == []


def test_rss_high_quality_top_up_does_not_run_when_cache_already_satisfies_target(tmp_path) -> None:
    coord = RSSCoordinator(
        feed_urls=[],
        cache_dir=tmp_path / "rss_cache",
        target_total_images=30,
        min_refresh_target=11,
    )
    coord._cache._images = [_build_cached_image(i, coord.cache_dir) for i in range(30)]

    calls: list[tuple[str, int]] = []
    coord._process_single_feed = lambda feed_url, max_images, existing_paths: calls.append((feed_url, max_images)) or []  # type: ignore[method-assign]

    result = coord._top_up_with_high_quality_feeds(
        current_new=[],
        processed_urls=[
            "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
            "https://www.nasa.gov/feeds/iotd-feed",
        ],
        existing_paths=set(),
    )

    assert result == []
    assert calls == []
