"""Tests for RssPipelineManager generation token and dedupe functionality.

Phase 6.2.4: Test coverage for generation property, is_duplicate with logging,
and cache clear increments generation.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.rss.pipeline_manager import RssPipelineManager, get_rss_pipeline_manager
from sources.base_provider import ImageMetadata, ImageSourceType


class TestRssPipelineManagerGeneration:
    """Tests for generation token functionality (Phase 2.3)."""

    @pytest.fixture
    def fresh_manager(self):
        """Create a fresh RssPipelineManager instance for testing."""
        # Reset singleton for clean test state
        RssPipelineManager._instance = None
        manager = RssPipelineManager.get_instance()
        yield manager
        # Cleanup
        RssPipelineManager._instance = None

    def test_initial_generation_is_zero(self, fresh_manager):
        """Generation starts at 0."""
        assert fresh_manager.generation == 0

    def test_generation_increments_on_disk_cache_clear(self, fresh_manager):
        """Clearing disk cache increments generation."""
        initial_gen = fresh_manager.generation
        
        with patch.object(fresh_manager, '_clear_disk_cache', return_value=0):
            fresh_manager.clear_cache(clear_disk=True, clear_memory=False)
        
        assert fresh_manager.generation == initial_gen + 1

    def test_generation_not_incremented_on_memory_only_clear(self, fresh_manager):
        """Clearing only memory cache does NOT increment generation."""
        initial_gen = fresh_manager.generation
        
        fresh_manager.clear_cache(clear_disk=False, clear_memory=True)
        
        assert fresh_manager.generation == initial_gen

    def test_multiple_cache_clears_increment_generation(self, fresh_manager):
        """Multiple cache clears increment generation each time."""
        with patch.object(fresh_manager, '_clear_disk_cache', return_value=0):
            for i in range(3):
                fresh_manager.clear_cache(clear_disk=True, clear_memory=False)
        
        assert fresh_manager.generation == 3

    def test_generation_is_thread_safe(self, fresh_manager):
        """Generation access is protected by lock."""
        import threading
        
        results = []
        
        def increment_and_read():
            with patch.object(fresh_manager, '_clear_disk_cache', return_value=0):
                fresh_manager.clear_cache(clear_disk=True, clear_memory=False)
            results.append(fresh_manager.generation)
        
        threads = [threading.Thread(target=increment_and_read) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All threads should see monotonically increasing generations
        assert fresh_manager.generation == 5


class TestRssPipelineManagerDedupe:
    """Tests for is_duplicate with log_decision parameter."""

    @pytest.fixture
    def manager_with_keys(self):
        """Create manager with some recorded keys."""
        RssPipelineManager._instance = None
        manager = RssPipelineManager.get_instance()
        
        # Record some keys using record_keys (build_image_key prepends "url:" to URLs)
        manager.record_keys(["url:http://example.com/image1.jpg", "url:http://example.com/image2.jpg"])
        
        yield manager
        RssPipelineManager._instance = None

    def test_is_duplicate_returns_false_for_new_image(self, manager_with_keys):
        """New images are not duplicates."""
        image = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="test",
            image_id="new_image",
            url="http://example.com/new_image.jpg",
            title="New Image",
        )
        
        assert manager_with_keys.is_duplicate(image) is False

    def test_is_duplicate_returns_true_for_recorded_key(self, manager_with_keys):
        """Images with recorded keys are duplicates."""
        image = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="test",
            image_id="image1",
            url="http://example.com/image1.jpg",
            title="Image 1",
        )
        
        assert manager_with_keys.is_duplicate(image) is True

    def test_is_duplicate_with_pending_keys(self, manager_with_keys):
        """Pending keys are treated as duplicates."""
        image = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="test",
            image_id="pending",
            url="http://example.com/pending.jpg",
            title="Pending",
        )
        
        pending = {"url:http://example.com/pending.jpg"}
        assert manager_with_keys.is_duplicate(image, pending_keys=pending) is True

    def test_is_duplicate_log_decision_logs_duplicate(self, manager_with_keys, caplog):
        """log_decision=True logs duplicate decisions."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        image = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="test",
            image_id="image1",
            url="http://example.com/image1.jpg",
            title="Image 1",
        )
        
        manager_with_keys.is_duplicate(image, log_decision=True)
        
        assert "[DEDUPE]" in caplog.text or "Duplicate" in caplog.text

    def test_is_duplicate_log_decision_no_log_for_new(self, manager_with_keys, caplog):
        """log_decision=True does not log for non-duplicates."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        image = ImageMetadata(
            source_type=ImageSourceType.RSS,
            source_id="test",
            image_id="brand_new",
            url="http://example.com/brand_new.jpg",
            title="Brand New",
        )
        
        result = manager_with_keys.is_duplicate(image, log_decision=True)
        
        assert result is False
        # Should not log anything for non-duplicates

    def test_is_duplicate_returns_false_for_none(self, manager_with_keys):
        """None images are not duplicates."""
        assert manager_with_keys.is_duplicate(None) is False


class TestRssPipelineManagerCacheInvalidation:
    """Tests for cache invalidation via generation token."""

    @pytest.fixture
    def manager(self):
        """Create fresh manager."""
        RssPipelineManager._instance = None
        manager = RssPipelineManager.get_instance()
        yield manager
        RssPipelineManager._instance = None

    def test_clear_cache_returns_stats(self, manager):
        """clear_cache returns dictionary with stats."""
        with patch.object(manager, '_clear_disk_cache', return_value=5):
            result = manager.clear_cache(clear_disk=True, clear_memory=False)
        
        assert isinstance(result, dict)
        assert 'disk_files_removed' in result
        assert result['disk_files_removed'] == 5

    def test_clear_dedupe_clears_namespace(self, manager):
        """clear_dedupe clears keys for specific namespace."""
        manager.record_keys(["key1", "key2"], namespace="test_ns")
        
        assert manager.has_key("key1", namespace="test_ns")
        
        manager.clear_dedupe(namespace="test_ns")
        
        assert not manager.has_key("key1", namespace="test_ns")

    def test_helper_accessor_returns_singleton(self):
        """get_rss_pipeline_manager returns singleton instance."""
        RssPipelineManager._instance = None
        
        m1 = get_rss_pipeline_manager()
        m2 = get_rss_pipeline_manager()
        
        assert m1 is m2
        
        RssPipelineManager._instance = None
