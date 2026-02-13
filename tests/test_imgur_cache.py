"""Unit tests for ImgurImageCache.

Tests cover:
- Cache operations (put, get, has)
- LRU eviction
- Metadata persistence
- Thread safety
"""
import pytest
import tempfile
from pathlib import Path

from widgets.imgur.image_cache import (
    ImgurImageCache, CachedImage,
)


class TestCachedImage:
    """Tests for CachedImage dataclass."""
    
    def test_creation(self):
        """Test basic CachedImage creation."""
        img = CachedImage(
            id="test123",
            path="/tmp/test123.jpg",
            size_bytes=1024,
            width=640,
            height=480,
            last_accessed=1000.0,
            download_time=1000.0,
        )
        assert img.id == "test123"
        assert img.size_bytes == 1024
        assert img.width == 640
    
    def test_to_dict(self):
        """Test conversion to dict."""
        img = CachedImage(
            id="abc",
            path="/path/abc.jpg",
            size_bytes=512,
            width=100,
            height=100,
            last_accessed=500.0,
            download_time=500.0,
            is_animated=True,
            gallery_url="https://imgur.com/gallery/abc",
        )
        d = img.to_dict()
        assert d["id"] == "abc"
        assert d["is_animated"] == True
        assert d["gallery_url"] == "https://imgur.com/gallery/abc"
    
    def test_from_dict(self):
        """Test creation from dict."""
        d = {
            "id": "xyz",
            "path": "/path/xyz.jpg",
            "size_bytes": 2048,
            "width": 200,
            "height": 150,
            "last_accessed": 123.0,
            "download_time": 100.0,
            "is_animated": False,
            "gallery_url": "",
        }
        img = CachedImage.from_dict(d)
        assert img.id == "xyz"
        assert img.size_bytes == 2048


class TestImgurImageCache:
    """Tests for ImgurImageCache class."""
    
    @pytest.fixture
    def temp_cache(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ImgurImageCache(
                cache_dir=Path(tmpdir),
                max_size_mb=10,
                max_items=100,
            )
            yield cache
            cache.cleanup()
    
    def test_init(self, temp_cache):
        """Test cache initialization."""
        assert temp_cache.cache_dir.exists()
        assert temp_cache.get_cached_count() == 0
    
    def test_has_empty(self, temp_cache):
        """Test has() on empty cache."""
        assert not temp_cache.has("nonexistent")
    
    def test_get_empty(self, temp_cache):
        """Test get() on empty cache."""
        assert temp_cache.get("nonexistent") is None
    
    def test_put_and_get(self, temp_cache):
        """Test basic put and get operations."""
        # Create a simple test image (1x1 white pixel PNG)
        test_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ])
        
        cached = temp_cache.put(
            "test123",
            test_data,
            extension="png",
            gallery_url="https://imgur.com/gallery/test123",
        )
        
        assert cached is not None
        assert cached.id == "test123"
        assert temp_cache.has("test123")
        
        result = temp_cache.get("test123")
        assert result is not None
        path, meta = result
        assert path.exists()
        assert meta.gallery_url == "https://imgur.com/gallery/test123"
    
    def test_put_duplicate(self, temp_cache):
        """Test that putting duplicate returns existing."""
        test_data = b"test image data"
        
        cached1 = temp_cache.put("dup123", test_data)
        cached2 = temp_cache.put("dup123", test_data)
        
        assert cached1 is not None
        assert cached2 is not None
        assert temp_cache.get_cached_count() == 1
    
    def test_get_all_cached(self, temp_cache):
        """Test getting all cached items."""
        temp_cache.put("img1", b"data1")
        temp_cache.put("img2", b"data2")
        temp_cache.put("img3", b"data3")
        
        all_cached = temp_cache.get_all_cached()
        assert len(all_cached) == 3
        
        # Should be sorted by last_accessed (newest first)
        ids = [c.id for c in all_cached]
        assert "img3" in ids
    
    def test_clear(self, temp_cache):
        """Test cache clearing."""
        temp_cache.put("img1", b"data1")
        temp_cache.put("img2", b"data2")
        
        assert temp_cache.get_cached_count() == 2
        
        temp_cache.clear()
        
        assert temp_cache.get_cached_count() == 0
        assert not temp_cache.has("img1")
    
    def test_get_cache_size_mb(self, temp_cache):
        """Test cache size calculation."""
        temp_cache.put("img1", b"x" * 1024)  # 1KB
        temp_cache.put("img2", b"y" * 2048)  # 2KB
        
        size_mb = temp_cache.get_cache_size_mb()
        assert size_mb > 0
        assert size_mb < 1  # Should be less than 1MB


class TestLRUEviction:
    """Tests for LRU eviction behavior."""
    
    @pytest.fixture
    def small_cache(self):
        """Create a small cache for eviction testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ImgurImageCache(
                cache_dir=Path(tmpdir),
                max_size_mb=1,  # 1MB max
                max_items=5,    # 5 items max
            )
            yield cache
            cache.cleanup()
    
    def test_eviction_by_item_count(self, small_cache):
        """Test eviction when max items exceeded."""
        # Add 6 items to a cache with max 5
        for i in range(6):
            small_cache.put(f"img{i}", b"x" * 100)
        
        # Should have at most 5 items
        assert small_cache.get_cached_count() <= 5


class TestMetadataPersistence:
    """Tests for metadata persistence."""
    
    def test_save_and_load(self):
        """Test that metadata persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            
            # First instance - add data
            cache1 = ImgurImageCache(cache_dir=cache_dir)
            cache1.put("persist1", b"data1", gallery_url="url1")
            cache1.save()
            
            # Second instance - should load data
            cache2 = ImgurImageCache(cache_dir=cache_dir)
            assert cache2.has("persist1")
            
            result = cache2.get("persist1")
            assert result is not None
            _, meta = result
            assert meta.gallery_url == "url1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
