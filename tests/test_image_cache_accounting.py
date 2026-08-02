"""Passive accounting tests for the existing image-cache behavior."""
import logging
import math

import pytest
from PySide6.QtGui import QImage, QPixmap

from utils.image_cache import ImageCache


def test_cache_entry_telemetry_uses_the_cache_family_when_enabled(monkeypatch, caplog):
    monkeypatch.setattr("utils.image_cache.is_cache_logging_enabled", lambda: True)
    monkeypatch.setattr("utils.image_cache.is_verbose_logging", lambda: False)
    cache = ImageCache(max_items=2)
    image = QImage(2, 2, QImage.Format.Format_ARGB32)

    with caplog.at_level(logging.INFO, logger="utils.image_cache"):
        cache.put("image", image)
        assert cache.get("image") is image
        assert cache.get("missing") is None

    assert "[CACHE] Cached: image" in caplog.text
    assert "[CACHE] Cache hit: image" in caplog.text
    assert "[CACHE] Cache miss: missing" in caplog.text


def test_qimage_exact_bytes_drive_the_retention_budget():
    cache = ImageCache(max_items=2, owner="decode-cache", generation=7)
    image = QImage(5, 2, QImage.Format.Format_RGB888)

    cache.put("image", image)

    assert cache.memory_usage() == image.sizeInBytes()
    assert cache.tracked_memory_usage() == image.sizeInBytes()
    snapshot = cache.get_accounting_snapshot()
    assert snapshot["total_tracked_bytes"] == image.sizeInBytes()
    assert snapshot["resources"][0]["owner"] == "decode-cache"
    assert snapshot["resources"][0]["generation"] == 7
    assert snapshot["resources"][0]["dimensions"] == (5, 2)
    assert snapshot["resources"][0]["lease_count"] is None
    with pytest.raises(TypeError):
        snapshot["total_tracked_bytes"] = 0
    with pytest.raises(TypeError):
        snapshot["resources"][0]["tracked_bytes"] = 0


def test_qpixmap_exact_bytes_use_depth_rounding(qt_app):
    cache = ImageCache(max_items=2)
    pixmap = QPixmap(7, 3)

    cache.put("pixmap", pixmap)

    expected = 7 * 3 * math.ceil(pixmap.depth() / 8)
    assert cache.tracked_memory_usage() == expected
    entry = cache.get_accounting_snapshot()["resources"][0]
    assert entry["tracked_bytes"] == expected
    assert entry["format"] == f"QPixmap(depth={pixmap.depth()})"


def test_exact_counter_follows_replacement_eviction_remove_and_clear():
    cache = ImageCache(max_items=1)
    first = QImage(3, 2, QImage.Format.Format_RGB888)
    replacement = QImage(4, 2, QImage.Format.Format_Grayscale8)

    cache.put("same", first)
    cache.put("same", replacement)
    assert cache.tracked_memory_usage() == replacement.sizeInBytes()

    other = QImage(2, 2, QImage.Format.Format_ARGB32)
    cache.put("other", other)
    assert not cache.contains("same")
    assert cache.tracked_memory_usage() == other.sizeInBytes()

    assert cache.remove("other") is True
    assert cache.tracked_memory_usage() == 0
    cache.put("again", first)
    cache.clear()
    assert cache.tracked_memory_usage() == 0


def test_identical_put_reuses_existing_entry_without_metadata_churn():
    cache = ImageCache(max_items=2)
    image = QImage(8, 8, QImage.Format.Format_ARGB32)

    cache.put("same", image)
    initial_snapshot = cache.get_accounting_snapshot()
    cache.put("same", image)

    stats = cache.get_stats()
    assert cache.get_accounting_snapshot()["resources"][0] is initial_snapshot["resources"][0]
    assert stats["replacements"] == 0
    assert stats["idempotent_puts_avoided"] == 1
    assert cache.tracked_memory_usage() == image.sizeInBytes()


def test_snapshot_reads_precomputed_metadata_not_live_qt_objects():
    cache = ImageCache(max_items=1)
    image = QImage(3, 2, QImage.Format.Format_RGB888)
    cache.put("image", image)

    class _ExplodingImage:
        def width(self):
            raise AssertionError("snapshot touched live image")

        def height(self):
            raise AssertionError("snapshot touched live image")

        def depth(self):
            raise AssertionError("snapshot touched live image")

    cache._cache["image"] = _ExplodingImage()
    snapshot = cache.get_accounting_snapshot()

    assert snapshot["resources"][0]["dimensions"] == (3, 2)
    assert snapshot["resources"][0]["tracked_bytes"] == image.sizeInBytes()


def test_exact_byte_budget_evicts_even_below_item_limit():
    one_image_bytes = QImage(64, 64, QImage.Format.Format_ARGB32).sizeInBytes()
    cache = ImageCache(
        max_items=10,
        max_memory_mb=(one_image_bytes + 1) / (1024 * 1024),
    )
    first = QImage(64, 64, QImage.Format.Format_ARGB32)
    second = QImage(64, 64, QImage.Format.Format_ARGB32)

    cache.put("first", first)
    cache.put("second", second)

    assert not cache.contains("first")
    assert cache.contains("second")
    assert cache.memory_usage() == second.sizeInBytes()
    assert cache.memory_usage() <= cache.max_memory_bytes


def test_cache_stats_separate_raw_and_display_ready_churn():
    image = QImage(4, 4, QImage.Format.Format_ARGB32)
    cache = ImageCache(max_items=2)

    cache.put("source-a.jpg", image)
    cache.put("source-a.jpg|scaled:fill:4x4:l0:s0", image.copy())
    cache.put("source-b.jpg|scaled:fill:4x4:l0:s0", image.copy())

    stats = cache.get_stats()
    assert stats["raw_items"] == 0
    assert stats["scaled_items"] == 2
    assert stats["raw_evictions"] == 1
    assert stats["scaled_evictions"] == 0
    assert stats["raw_evicted_bytes"] == image.sizeInBytes()
    assert stats["scaled_bytes"] == image.sizeInBytes() * 2
