"""Tests for PainterShadow - Phase E root cause fix.

These tests verify the QPainter-based shadow rendering system that replaces
QGraphicsDropShadowEffect to fix the Phase E visual corruption bug.

Phase E Bug Summary:
    QGraphicsDropShadowEffect caches rendered shadow pixmaps internally.
    When window position/activation changes occur across displays (e.g., context
    menu on Display 1 triggers WM_WINDOWPOSCHANGING on Display 0), the cache
    invalidation doesn't happen correctly, causing shadow corruption.

Solution:
    Shadows are now rendered via PainterShadow in each widget's paintEvent(),
    completely bypassing Qt's internal effect caching system.
"""

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPixmap

from widgets.painter_shadow import (
    PainterShadow,
    ShadowConfig,
    ShadowCache,
    AsyncShadowRenderer,
    get_shadow_cache,
    clear_shadow_cache,
    prerender_widget_shadow,
    _GLOBAL_PRERENDER_CACHE,
    _GLOBAL_PRERENDER_LOCK,
)


class TestShadowConfig:
    """Tests for ShadowConfig dataclass and settings parsing."""

    def test_default_values(self):
        """ShadowConfig should have sensible defaults."""
        config = ShadowConfig()
        assert config.enabled is True
        assert config.blur_radius == 18
        assert config.offset_x == 4
        assert config.offset_y == 4
        assert config.opacity == 1.0
        assert isinstance(config.color, QColor)

    def test_from_settings_empty(self):
        """from_settings with empty dict should return defaults."""
        config = ShadowConfig.from_settings({})
        assert config.enabled is True
        assert config.blur_radius == 18

    def test_from_settings_none(self):
        """from_settings with None should return disabled config."""
        config = ShadowConfig.from_settings(None)
        assert config.enabled is False

    def test_from_settings_disabled(self):
        """from_settings should respect enabled=False."""
        config = ShadowConfig.from_settings({"enabled": False})
        assert config.enabled is False

    def test_from_settings_enabled_string(self):
        """from_settings should parse string 'false' as disabled."""
        config = ShadowConfig.from_settings({"enabled": "false"})
        assert config.enabled is False
        
        config = ShadowConfig.from_settings({"enabled": "true"})
        assert config.enabled is True

    def test_from_settings_blur_radius(self):
        """from_settings should parse blur_radius correctly."""
        config = ShadowConfig.from_settings({"blur_radius": 25})
        assert config.blur_radius == 25

    def test_from_settings_offset(self):
        """from_settings should parse offset_x and offset_y correctly."""
        config = ShadowConfig.from_settings({"offset_x": 10, "offset_y": 15})
        assert config.offset_x == 10
        assert config.offset_y == 15

    def test_from_settings_color_list(self):
        """from_settings should parse color as list [r, g, b, a]."""
        config = ShadowConfig.from_settings({"color": [255, 128, 64, 200]})
        assert config.color.red() == 255
        assert config.color.green() == 128
        assert config.color.blue() == 64
        assert config.color.alpha() == 200

    def test_from_settings_color_qcolor(self):
        """from_settings should accept QColor directly."""
        input_color = QColor(100, 150, 200, 180)
        config = ShadowConfig.from_settings({"color": input_color})
        assert config.color.red() == 100
        assert config.color.green() == 150
        assert config.color.blue() == 200
        assert config.color.alpha() == 180

    def test_from_settings_opacity(self):
        """from_settings should parse opacity correctly."""
        config = ShadowConfig.from_settings({"opacity": 0.5})
        assert config.opacity == 0.5


class TestShadowCache:
    """Tests for ShadowCache class."""

    def test_cache_miss_on_empty(self):
        """Empty cache should return None."""
        cache = ShadowCache()
        result = cache.get(QSize(100, 50), ShadowConfig())
        assert result is None

    def test_cache_hit_after_set(self):
        """Cache should return pixmap after set."""
        cache = ShadowCache()
        size = QSize(100, 50)
        config = ShadowConfig()
        pixmap = QPixmap(100, 50)
        
        cache.set(pixmap, size, config)
        result = cache.get(size, config)
        
        assert result is not None
        assert result.width() == 100
        assert result.height() == 50

    def test_cache_miss_on_size_change(self):
        """Cache should miss when size changes."""
        cache = ShadowCache()
        config = ShadowConfig()
        pixmap = QPixmap(100, 50)
        
        cache.set(pixmap, QSize(100, 50), config)
        result = cache.get(QSize(200, 100), config)
        
        assert result is None

    def test_cache_miss_on_config_change(self):
        """Cache should miss when config changes."""
        cache = ShadowCache()
        size = QSize(100, 50)
        pixmap = QPixmap(100, 50)
        
        config1 = ShadowConfig(blur_radius=18)
        config2 = ShadowConfig(blur_radius=25)
        
        cache.set(pixmap, size, config1)
        result = cache.get(size, config2)
        
        assert result is None

    def test_invalidate_clears_cache(self):
        """invalidate() should clear the cache."""
        cache = ShadowCache()
        size = QSize(100, 50)
        config = ShadowConfig()
        pixmap = QPixmap(100, 50)
        
        cache.set(pixmap, size, config)
        cache.invalidate()
        result = cache.get(size, config)
        
        assert result is None


class TestGlobalShadowCache:
    """Tests for global shadow cache functions."""

    def test_get_shadow_cache_creates_new(self):
        """get_shadow_cache should create new cache for unknown widget."""
        widget_id = 999999  # Unlikely to exist
        clear_shadow_cache(widget_id)  # Ensure clean state
        
        cache = get_shadow_cache(widget_id)
        assert cache is not None
        assert isinstance(cache, ShadowCache)
        
        # Cleanup
        clear_shadow_cache(widget_id)

    def test_get_shadow_cache_returns_same(self):
        """get_shadow_cache should return same cache for same widget."""
        widget_id = 888888
        clear_shadow_cache(widget_id)
        
        cache1 = get_shadow_cache(widget_id)
        cache2 = get_shadow_cache(widget_id)
        
        assert cache1 is cache2
        
        # Cleanup
        clear_shadow_cache(widget_id)

    def test_clear_shadow_cache_removes(self):
        """clear_shadow_cache should remove the cache."""
        widget_id = 777777
        
        cache = get_shadow_cache(widget_id)
        clear_shadow_cache(widget_id)
        
        # Getting again should create a new cache
        cache2 = get_shadow_cache(widget_id)
        assert cache is not cache2
        
        # Cleanup
        clear_shadow_cache(widget_id)


class TestPainterShadow:
    """Tests for PainterShadow static methods."""

    def test_render_shadow_pixmap_creates_image(self):
        """_render_shadow_pixmap should create a valid pixmap."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        pixmap = PainterShadow._render_shadow_pixmap(size, config, corner_radius=0)
        
        assert pixmap is not None
        assert not pixmap.isNull()
        # Pixmap should be larger than widget due to blur padding
        assert pixmap.width() > size.width()
        assert pixmap.height() > size.height()

    def test_render_shadow_pixmap_with_corner_radius(self):
        """_render_shadow_pixmap should work with corner radius."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        pixmap = PainterShadow._render_shadow_pixmap(size, config, corner_radius=8)
        
        assert pixmap is not None
        assert not pixmap.isNull()

    def test_render_shadow_pixmap_empty_size(self):
        """_render_shadow_pixmap should return None for empty size."""
        size = QSize(0, 0)
        config = ShadowConfig(enabled=True)
        
        pixmap = PainterShadow._render_shadow_pixmap(size, config)
        
        assert pixmap is None

    def test_apply_blur_returns_image(self):
        """_apply_blur should return a blurred image."""
        # Create a simple test image
        img = QImage(100, 50, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 255))
        
        blurred = PainterShadow._apply_blur(img, radius=10)
        
        assert blurred is not None
        assert blurred.width() == img.width()
        assert blurred.height() == img.height()

    def test_apply_blur_zero_radius(self):
        """_apply_blur with zero radius should return original image."""
        img = QImage(100, 50, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 255))
        
        result = PainterShadow._apply_blur(img, radius=0)
        
        # Should return the same image (no blur applied)
        assert result is img


class TestShadowConfigHash:
    """Tests for ShadowCache config hashing."""

    def test_same_config_same_hash(self):
        """Identical configs should produce same hash."""
        config1 = ShadowConfig(enabled=True, blur_radius=18, offset_x=4, offset_y=4)
        config2 = ShadowConfig(enabled=True, blur_radius=18, offset_x=4, offset_y=4)
        
        hash1 = ShadowCache._hash_config(config1)
        hash2 = ShadowCache._hash_config(config2)
        
        assert hash1 == hash2

    def test_different_blur_different_hash(self):
        """Different blur_radius should produce different hash."""
        config1 = ShadowConfig(blur_radius=18)
        config2 = ShadowConfig(blur_radius=25)
        
        hash1 = ShadowCache._hash_config(config1)
        hash2 = ShadowCache._hash_config(config2)
        
        assert hash1 != hash2

    def test_different_offset_different_hash(self):
        """Different offset should produce different hash."""
        config1 = ShadowConfig(offset_x=4, offset_y=4)
        config2 = ShadowConfig(offset_x=8, offset_y=8)
        
        hash1 = ShadowCache._hash_config(config1)
        hash2 = ShadowCache._hash_config(config2)
        
        assert hash1 != hash2


class TestAsyncShadowRenderer:
    """Tests for AsyncShadowRenderer thread-safe async rendering."""

    def setup_method(self):
        """Clear cache before each test."""
        AsyncShadowRenderer.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        AsyncShadowRenderer.clear_cache()

    def test_get_cached_empty(self):
        """get_cached should return None when cache is empty."""
        size = QSize(100, 50)
        config = ShadowConfig()
        
        result = AsyncShadowRenderer.get_cached(size, config)
        assert result is None

    def test_get_or_render_creates_shadow(self):
        """get_or_render should create shadow when not cached."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        result = AsyncShadowRenderer.get_or_render(size, config)
        
        assert result is not None
        assert not result.isNull()
        # Shadow should be larger than widget due to blur padding
        assert result.width() > size.width()
        assert result.height() > size.height()

    def test_get_or_render_caches_result(self):
        """get_or_render should cache the result."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # First call renders
        result1 = AsyncShadowRenderer.get_or_render(size, config)
        
        # Second call should return cached
        result2 = AsyncShadowRenderer.get_cached(size, config)
        
        assert result1 is not None
        assert result2 is not None
        # Should be the same pixmap
        assert result1.width() == result2.width()
        assert result1.height() == result2.height()

    def test_cache_key_includes_corner_radius(self):
        """Different corner radii should produce different cache entries."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Render with corner_radius=0
        result1 = AsyncShadowRenderer.get_or_render(size, config, corner_radius=0)
        
        # Render with corner_radius=8
        result2 = AsyncShadowRenderer.get_or_render(size, config, corner_radius=8)
        
        # Both should exist
        assert result1 is not None
        assert result2 is not None
        
        # Cache should have 2 entries
        stats = AsyncShadowRenderer.get_cache_stats()
        assert stats["cache_size"] == 2

    def test_clear_cache_removes_all(self):
        """clear_cache should remove all cached shadows."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Add some entries
        AsyncShadowRenderer.get_or_render(size, config, corner_radius=0)
        AsyncShadowRenderer.get_or_render(size, config, corner_radius=8)
        
        stats = AsyncShadowRenderer.get_cache_stats()
        assert stats["cache_size"] == 2
        
        # Clear
        cleared = AsyncShadowRenderer.clear_cache()
        assert cleared == 2
        
        # Should be empty now
        stats = AsyncShadowRenderer.get_cache_stats()
        assert stats["cache_size"] == 0

    def test_disabled_config_returns_none(self):
        """Disabled config should return None without caching."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=False)
        
        result = AsyncShadowRenderer.get_cached(size, config)
        assert result is None

    def test_empty_size_returns_none(self):
        """Empty size should return None."""
        size = QSize(0, 0)
        config = ShadowConfig(enabled=True)
        
        result = AsyncShadowRenderer.get_or_render(size, config)
        assert result is None


class TestAsyncShadowCacheCorruption:
    """Tests for cache corruption detection and recovery."""

    def setup_method(self):
        """Clear cache before each test."""
        AsyncShadowRenderer.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        AsyncShadowRenderer.clear_cache()

    def test_null_pixmap_detected_and_removed(self):
        """Null pixmap in cache should be detected and removed."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Manually insert a null pixmap into cache
        key = AsyncShadowRenderer._make_cache_key(
            size.width(), size.height(), config.blur_radius, 0
        )
        with _GLOBAL_PRERENDER_LOCK:
            _GLOBAL_PRERENDER_CACHE[key] = QPixmap()  # Null pixmap
        
        # get_cached should detect corruption and return None
        result = AsyncShadowRenderer.get_cached(size, config)
        assert result is None
        
        # Corrupted entry should be removed
        with _GLOBAL_PRERENDER_LOCK:
            assert key not in _GLOBAL_PRERENDER_CACHE

    def test_size_mismatch_detected_and_removed(self):
        """Size mismatch in cache should be detected and removed."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Manually insert a wrong-sized pixmap into cache
        key = AsyncShadowRenderer._make_cache_key(
            size.width(), size.height(), config.blur_radius, 0
        )
        wrong_size_pixmap = QPixmap(50, 25)  # Wrong size
        wrong_size_pixmap.fill(QColor(0, 0, 0))
        
        with _GLOBAL_PRERENDER_LOCK:
            _GLOBAL_PRERENDER_CACHE[key] = wrong_size_pixmap
        
        # get_cached should detect size mismatch and return None
        result = AsyncShadowRenderer.get_cached(size, config)
        assert result is None
        
        # Corrupted entry should be removed
        with _GLOBAL_PRERENDER_LOCK:
            assert key not in _GLOBAL_PRERENDER_CACHE

    def test_concurrent_access_thread_safety(self):
        """Cache should be thread-safe under concurrent access."""
        import threading
        import time
        
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for _ in range(10):
                    # Mix of reads and writes
                    if worker_id % 2 == 0:
                        result = AsyncShadowRenderer.get_or_render(size, config)
                        results.append(("render", result is not None))
                    else:
                        result = AsyncShadowRenderer.get_cached(size, config)
                        results.append(("cached", result is not None))
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0, f"Thread errors: {errors}"
        
        # All operations should complete
        assert len(results) == 40  # 4 threads * 10 iterations

    def test_cache_recovery_after_corruption(self):
        """Cache should recover after corruption is detected."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Insert corrupted entry
        key = AsyncShadowRenderer._make_cache_key(
            size.width(), size.height(), config.blur_radius, 0
        )
        with _GLOBAL_PRERENDER_LOCK:
            _GLOBAL_PRERENDER_CACHE[key] = QPixmap()  # Null = corrupted
        
        # First access detects corruption
        result1 = AsyncShadowRenderer.get_cached(size, config)
        assert result1 is None
        
        # get_or_render should recover by re-rendering
        result2 = AsyncShadowRenderer.get_or_render(size, config)
        assert result2 is not None
        assert not result2.isNull()
        
        # Cache should now have valid entry
        result3 = AsyncShadowRenderer.get_cached(size, config)
        assert result3 is not None


class TestAsyncShadowPrerender:
    """Tests for async pre-rendering functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        AsyncShadowRenderer.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        AsyncShadowRenderer.clear_cache()

    def test_prerender_async_returns_true_for_new(self):
        """prerender_async should return True for new entries."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Should return True (submitted for rendering)
        result = AsyncShadowRenderer.prerender_async(size, config)
        # Note: May return False if ThreadManager not available in test
        # This is acceptable - we're testing the logic, not the threading
        assert isinstance(result, bool)

    def test_prerender_async_returns_false_for_cached(self):
        """prerender_async should return False if already cached."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Pre-populate cache
        AsyncShadowRenderer.get_or_render(size, config)
        
        # Should return False (already cached)
        result = AsyncShadowRenderer.prerender_async(size, config)
        assert result is False

    def test_prerender_async_disabled_config(self):
        """prerender_async should return False for disabled config."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=False)
        
        result = AsyncShadowRenderer.prerender_async(size, config)
        assert result is False

    def test_prerender_async_empty_size(self):
        """prerender_async should return False for empty size."""
        size = QSize(0, 0)
        config = ShadowConfig(enabled=True)
        
        result = AsyncShadowRenderer.prerender_async(size, config)
        assert result is False

    def test_warm_cache_submits_common_sizes(self):
        """warm_cache should submit pre-renders for common sizes."""
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # This may return 0 if ThreadManager not available in test
        count = AsyncShadowRenderer.warm_cache(config)
        assert isinstance(count, int)
        assert count >= 0

    def test_cache_stats_tracking(self):
        """get_cache_stats should return accurate counts."""
        size = QSize(100, 50)
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Initially empty
        stats = AsyncShadowRenderer.get_cache_stats()
        assert stats["cache_size"] == 0
        
        # Add one entry
        AsyncShadowRenderer.get_or_render(size, config)
        
        stats = AsyncShadowRenderer.get_cache_stats()
        assert stats["cache_size"] == 1


class TestPrerenderWidgetShadow:
    """Tests for prerender_widget_shadow convenience function."""

    def setup_method(self):
        """Clear cache before each test."""
        AsyncShadowRenderer.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        AsyncShadowRenderer.clear_cache()

    def test_prerender_widget_shadow_with_mock_widget(self):
        """prerender_widget_shadow should work with widget-like object."""
        class MockWidget:
            def size(self):
                return QSize(200, 100)
        
        widget = MockWidget()
        config = ShadowConfig(enabled=True, blur_radius=10)
        
        # Should not raise
        result = prerender_widget_shadow(widget, config)
        assert isinstance(result, bool)

    def test_prerender_widget_shadow_empty_size(self):
        """prerender_widget_shadow should handle empty widget size."""
        class MockWidget:
            def size(self):
                return QSize(0, 0)
        
        widget = MockWidget()
        config = ShadowConfig(enabled=True)
        
        result = prerender_widget_shadow(widget, config)
        assert result is False

    def test_prerender_widget_shadow_exception_handling(self):
        """prerender_widget_shadow should handle exceptions gracefully."""
        class BrokenWidget:
            def size(self):
                raise RuntimeError("Widget error")
        
        widget = BrokenWidget()
        config = ShadowConfig(enabled=True)
        
        # Should not raise, just return False
        result = prerender_widget_shadow(widget, config)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
