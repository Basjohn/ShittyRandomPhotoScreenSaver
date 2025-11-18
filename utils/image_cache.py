"""
LRU (Least Recently Used) cache for images.

Caches decoded images to avoid redundant disk I/O and decoding.
Supports caching of QImage (thread-safe decode) and QPixmap (UI-ready).
"""
from collections import OrderedDict
import threading
from typing import Optional, Union
from PySide6.QtGui import QPixmap, QImage
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
    - Lightweight PERF counters (hits/misses/evictions) used by
      ``"[PERF] ImageCache"`` summary logs in ``ScreensaverEngine.stop()``;
      grep for that tag to gate/strip profiling in production builds.
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
        
        self._cache: OrderedDict[str, Union[QImage, QPixmap]] = OrderedDict()
        self._current_memory = 0
        # Lightweight telemetry counters (Route3 §6.4: cache profiling)
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._evict_count: int = 0
        self._lock = threading.RLock()
        
        logger.info(f"ImageCache initialized: max_items={max_items}, "
                   f"max_memory={max_memory_mb}MB")
    
    def get(self, key: str) -> Optional[Union[QImage, QPixmap]]:
        """
        Get an image from cache.
        
        Args:
            key: Cache key (usually file path)
        
        Returns:
            QPixmap if found, None otherwise
        """
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hit_count += 1
                logger.debug(f"Cache hit: {key}")
                return self._cache[key]
            
            self._miss_count += 1
            logger.debug(f"Cache miss: {key}")
            return None
    
    def put(self, key: str, image: Union[QImage, QPixmap]) -> None:
        """
        Add an image to cache.
        
        If cache is full, evicts least recently used entries.
        
        Args:
            key: Cache key (usually file path)
            pixmap: QPixmap to cache
        """
        # Remove if already exists (to update order)
        with self._lock:
            if key in self._cache:
                old_img = self._cache.pop(key)
                self._current_memory -= self._estimate_size(old_img)
            
            # Add new entry
            self._cache[key] = image
            self._current_memory += self._estimate_size(image)
            
            # Evict if necessary
            while self._should_evict_locked():
                self._evict_oldest_locked()
            
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
        with self._lock:
            return key in self._cache
    
    def remove(self, key: str) -> bool:
        """
        Remove an entry from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                pixmap = self._cache.pop(key)
                self._current_memory -= self._estimate_size(pixmap)
                logger.debug(f"Removed from cache: {key}")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached images."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._current_memory = 0
            logger.info(f"Cache cleared: {count} images removed")
    
    def size(self) -> int:
        """Get number of cached images."""
        with self._lock:
            return len(self._cache)
    
    def memory_usage(self) -> int:
        """Get approximate memory usage in bytes."""
        with self._lock:
            return self._current_memory
    
    def memory_usage_mb(self) -> float:
        """Get approximate memory usage in MB."""
        with self._lock:
            return self._current_memory / (1024 * 1024)
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            item_count = len(self._cache)
            memory_mb = self._current_memory / (1024 * 1024)
            max_memory_mb = self.max_memory_bytes / (1024 * 1024)
            total_accesses = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_accesses * 100.0) if total_accesses > 0 else 0.0

            return {
                'item_count': item_count,
                'max_items': self.max_items,
                'memory_usage_mb': memory_mb,
                'max_memory_mb': max_memory_mb,
                'utilization_percent': (item_count / self.max_items) * 100 if self.max_items > 0 else 0.0,
                'hits': self._hit_count,
                'misses': self._miss_count,
                'hit_rate_percent': hit_rate,
                'evictions': self._evict_count,
            }
    
    def _should_evict_locked(self) -> bool:
        """Check if eviction is needed (caller holds lock)."""
        return (len(self._cache) > self.max_items or 
                self._current_memory > self.max_memory_bytes)
    
    def _evict_oldest_locked(self) -> None:
        """Evict the least recently used entry (caller holds lock)."""
        if not self._cache:
            return
        key, img = self._cache.popitem(last=False)
        self._current_memory -= self._estimate_size(img)
        self._evict_count += 1
        logger.debug(f"Evicted from cache: {key}")
    
    def _estimate_size(self, image: Union[QImage, QPixmap]) -> int:
        """
        Estimate memory size of a QPixmap.
        
        Args:
            pixmap: QPixmap to estimate
        
        Returns:
            Estimated size in bytes
        """
        # Handle null/invalid images
        if (isinstance(image, QPixmap) and image.isNull()) or (isinstance(image, QImage) and image.isNull()):
            return 0
        
        # Estimate: width * height * bytes_per_pixel
        # Assume 4 bytes per pixel (RGBA)
        width = image.width()
        height = image.height()
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
