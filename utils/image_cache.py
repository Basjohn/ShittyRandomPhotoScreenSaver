"""
LRU (Least Recently Used) cache for QPixmap images.

Caches loaded images to avoid redundant disk I/O and image decoding.
"""
from collections import OrderedDict
from typing import Optional
from PySide6.QtGui import QPixmap
from core.logging.logger import get_logger

logger = get_logger(__name__)


class ImageCache:
    """
    LRU cache for QPixmap objects.
    
    Features:
    - Automatic size management (evicts oldest entries when full)
    - Memory-efficient (stores references, not copies)
    - Thread-safe for single writer, multiple readers
    - Size tracking for memory management
    """
    
    def __init__(self, max_items: int = 10, max_memory_mb: int = 500):
        """
        Initialize image cache.
        
        Args:
            max_items: Maximum number of images to cache
            max_memory_mb: Maximum memory to use (approximate, in MB)
        """
        self.max_items = max_items
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._current_memory = 0
        
        logger.info(f"ImageCache initialized: max_items={max_items}, "
                   f"max_memory={max_memory_mb}MB")
    
    def get(self, key: str) -> Optional[QPixmap]:
        """
        Get an image from cache.
        
        Args:
            key: Cache key (usually file path)
        
        Returns:
            QPixmap if found, None otherwise
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            logger.debug(f"Cache hit: {key}")
            return self._cache[key]
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    def put(self, key: str, pixmap: QPixmap) -> None:
        """
        Add an image to cache.
        
        If cache is full, evicts least recently used entries.
        
        Args:
            key: Cache key (usually file path)
            pixmap: QPixmap to cache
        """
        # Remove if already exists (to update order)
        if key in self._cache:
            old_pixmap = self._cache.pop(key)
            self._current_memory -= self._estimate_size(old_pixmap)
        
        # Add new entry
        self._cache[key] = pixmap
        self._current_memory += self._estimate_size(pixmap)
        
        # Evict if necessary
        while self._should_evict():
            self._evict_oldest()
        
        logger.debug(f"Cached: {key} (size={len(self._cache)}/{self.max_items}, "
                    f"memory={self._current_memory / (1024*1024):.1f}MB)")
    
    def contains(self, key: str) -> bool:
        """
        Check if key is in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if key is cached
        """
        return key in self._cache
    
    def remove(self, key: str) -> bool:
        """
        Remove an entry from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if entry was removed, False if not found
        """
        if key in self._cache:
            pixmap = self._cache.pop(key)
            self._current_memory -= self._estimate_size(pixmap)
            logger.debug(f"Removed from cache: {key}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cached images."""
        count = len(self._cache)
        self._cache.clear()
        self._current_memory = 0
        logger.info(f"Cache cleared: {count} images removed")
    
    def size(self) -> int:
        """Get number of cached images."""
        return len(self._cache)
    
    def memory_usage(self) -> int:
        """Get approximate memory usage in bytes."""
        return self._current_memory
    
    def memory_usage_mb(self) -> float:
        """Get approximate memory usage in MB."""
        return self._current_memory / (1024 * 1024)
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        return {
            'item_count': len(self._cache),
            'max_items': self.max_items,
            'memory_usage_mb': self.memory_usage_mb(),
            'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
            'utilization_percent': (len(self._cache) / self.max_items) * 100 if self.max_items > 0 else 0
        }
    
    def _should_evict(self) -> bool:
        """Check if eviction is needed."""
        return (len(self._cache) > self.max_items or 
                self._current_memory > self.max_memory_bytes)
    
    def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return
        
        # Pop first item (oldest)
        key, pixmap = self._cache.popitem(last=False)
        self._current_memory -= self._estimate_size(pixmap)
        logger.debug(f"Evicted from cache: {key}")
    
    def _estimate_size(self, pixmap: QPixmap) -> int:
        """
        Estimate memory size of a QPixmap.
        
        Args:
            pixmap: QPixmap to estimate
        
        Returns:
            Estimated size in bytes
        """
        if pixmap.isNull():
            return 0
        
        # Estimate: width * height * bytes_per_pixel
        # Assume 4 bytes per pixel (RGBA)
        width = pixmap.width()
        height = pixmap.height()
        return width * height * 4
    
    def __len__(self) -> int:
        """Get number of cached images."""
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return key in self._cache
    
    def __str__(self) -> str:
        """String representation."""
        return (f"ImageCache(items={len(self._cache)}/{self.max_items}, "
                f"memory={self.memory_usage_mb():.1f}MB/"
                f"{self.max_memory_bytes / (1024*1024):.0f}MB)")
