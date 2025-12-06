"""
Tests for QPixmap/QImage pooling in ResourceManager.

These tests require a Qt application context for QPixmap/QImage.
"""
import pytest
from PySide6.QtGui import QPixmap, QImage

from core.resources.manager import ResourceManager


@pytest.fixture
def rm(qt_app):
    """Create a ResourceManager for testing."""
    manager = ResourceManager()
    yield manager
    try:
        manager.shutdown()
    except Exception:
        pass


class TestPixmapPooling:
    """Tests for QPixmap pooling."""
    
    def test_acquire_returns_none_when_empty(self, rm):
        """Acquire should return None when pool is empty."""
        result = rm.acquire_pixmap(100, 100)
        assert result is None
    
    def test_release_and_acquire(self, rm, qt_app):
        """Released pixmap should be acquirable."""
        pixmap = QPixmap(100, 100)
        
        # Release to pool
        released = rm.release_pixmap(pixmap)
        assert released is True
        
        # Acquire from pool
        acquired = rm.acquire_pixmap(100, 100)
        assert acquired is not None
        assert acquired.width() == 100
        assert acquired.height() == 100
    
    def test_pool_size_limit(self, rm, qt_app):
        """Pool should respect max size limit."""
        # Release more than max
        for i in range(rm.PIXMAP_POOL_MAX_SIZE + 5):
            pixmap = QPixmap(50, 50)
            rm.release_pixmap(pixmap)
        
        # Check pool stats
        stats = rm.get_pool_stats()
        assert stats["pixmap_pool_size"] <= rm.PIXMAP_POOL_MAX_SIZE
    
    def test_pool_stats_tracking(self, rm, qt_app):
        """Pool should track hits and misses."""
        # Miss (empty pool)
        rm.acquire_pixmap(100, 100)
        
        # Release and hit
        pixmap = QPixmap(100, 100)
        rm.release_pixmap(pixmap)
        rm.acquire_pixmap(100, 100)
        
        stats = rm.get_pool_stats()
        assert stats["pixmap_misses"] >= 1
        assert stats["pixmap_hits"] >= 1
    
    def test_different_sizes_separate_buckets(self, rm, qt_app):
        """Different sizes should use separate buckets."""
        # Release different sizes
        rm.release_pixmap(QPixmap(100, 100))
        rm.release_pixmap(QPixmap(200, 200))
        
        stats = rm.get_pool_stats()
        assert stats["pixmap_buckets"] == 2


class TestImagePooling:
    """Tests for QImage pooling."""
    
    def test_acquire_returns_none_when_empty(self, rm):
        """Acquire should return None when pool is empty."""
        result = rm.acquire_image(100, 100)
        assert result is None
    
    def test_release_and_acquire(self, rm):
        """Released image should be acquirable."""
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        
        # Release to pool
        released = rm.release_image(image)
        assert released is True
        
        # Acquire from pool
        acquired = rm.acquire_image(100, 100)
        assert acquired is not None
        assert acquired.width() == 100
        assert acquired.height() == 100


class TestPoolCleanup:
    """Tests for pool cleanup."""
    
    def test_clear_pools(self, rm, qt_app):
        """clear_pools should empty all pools."""
        # Add items
        rm.release_pixmap(QPixmap(100, 100))
        rm.release_image(QImage(100, 100, QImage.Format.Format_ARGB32))
        
        # Clear
        rm.clear_pools()
        
        stats = rm.get_pool_stats()
        assert stats["pixmap_pool_size"] == 0
        assert stats["image_pool_size"] == 0
    
    def test_shutdown_clears_pools(self, qt_app):
        """shutdown should clear pools."""
        manager = ResourceManager()
        
        # Add items
        manager.release_pixmap(QPixmap(100, 100))
        
        # Shutdown
        manager.shutdown()
        
        # Stats should show empty (though manager is shut down)
        stats = manager.get_pool_stats()
        assert stats["pixmap_pool_size"] == 0
