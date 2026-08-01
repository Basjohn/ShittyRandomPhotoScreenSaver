"""
LRU (Least Recently Used) cache for images.

Caches decoded images to avoid redundant disk I/O and decoding.
Supports immutable QImage entries and legacy GUI-owned QPixmap entries with exact logical-byte eviction.
"""
from collections import OrderedDict
import math
import threading
from types import MappingProxyType
from typing import Optional, Union
from PySide6.QtGui import QPixmap, QImage
from core.logging.logger import (
    get_logger,
    is_cache_logging_enabled,
    is_verbose_logging,
)


def _freeze_snapshot_value(value):
    """Detach mutable metadata before exposing an immutable snapshot."""
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze_snapshot_value(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze_snapshot_value(item) for item in value)
    return repr(value)

logger = get_logger(__name__)


def _cache_trace(message: str, *args: object) -> None:
    """Route per-entry cache telemetry to the opt-in cache sidecar."""
    if is_cache_logging_enabled():
        logger.info("[CACHE] " + message, *args)
    elif is_verbose_logging():
        logger.debug(message, *args)


class ImageCache:
    """
    LRU cache for immutable QImage and legacy GUI-owned QPixmap objects.
    
    Features:
    - Automatic size management (evicts oldest entries when full)
    - Memory-efficient (stores references, not copies)
    - Thread-safe for single writer, multiple readers
    - Size tracking for memory management
    - Lightweight PERF counters (hits/misses/evictions) used by
      ``"[PERF] ImageCache"`` summary logs in ``ScreensaverEngine.stop()``;
      grep for that tag to gate/strip profiling in production builds.
    """
    
    def __init__(
        self,
        max_items: int = 10,
        max_memory_mb: int = 500,
        *,
        owner: str = "ImageCache",
        generation: object = None,
    ):
        """
        Initialize image cache.
        
        Args:
            max_items: Maximum number of images to cache
            max_memory_mb: Maximum exact logical image bytes to retain, in MiB
        """
        self.max_items = max(1, int(max_items))
        self.max_memory_bytes = max(1, int(float(max_memory_mb) * 1024 * 1024))
        
        self._cache: OrderedDict[str, Union[QImage, QPixmap]] = OrderedDict()
        self._current_memory = 0
        self._tracked_bytes_by_key: dict[str, int] = {}
        self._resource_metadata_by_key: dict[str, MappingProxyType] = {}
        self._current_tracked_bytes = 0
        self._owner = str(owner)
        self._generation = generation
        # Lightweight telemetry counters for cache profiling.
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
            Cached QImage/QPixmap if found, otherwise None
        """
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hit_count += 1
                _cache_trace("Cache hit: %s", key)
                return self._cache[key]
            
            self._miss_count += 1
            _cache_trace("Cache miss: %s", key)
            return None
    
    def put(self, key: str, image: Union[QImage, QPixmap]) -> None:
        """
        Add an image to cache.
        
        If cache is full, evicts least recently used entries.
        
        Args:
            key: Cache key (usually file path)
            image: immutable QImage or GUI-owned QPixmap to cache
        """
        # Remove if already exists (to update order)
        with self._lock:
            if key in self._cache:
                old_img = self._cache.pop(key)
                self._current_memory -= self._tracked_size(old_img)
                self._current_tracked_bytes -= self._tracked_bytes_by_key.pop(key, 0)
                self._resource_metadata_by_key.pop(key, None)
            
            # Add new entry
            self._cache[key] = image
            tracked_bytes = self._tracked_size(image)
            self._current_memory += tracked_bytes
            self._tracked_bytes_by_key[key] = tracked_bytes
            self._resource_metadata_by_key[key] = MappingProxyType({
                "key": key,
                "owner": self._owner,
                "generation": _freeze_snapshot_value(self._generation),
                "dimensions": (int(image.width()), int(image.height())),
                "format": self._image_format(image),
                "tracked_bytes": tracked_bytes,
                "lease_count": None,
            })
            self._current_tracked_bytes += tracked_bytes
            
            # Evict if necessary
            while self._should_evict_locked():
                self._evict_oldest_locked()
            
            _cache_trace(
                "Cached: %s (size=%d/%d, memory=%.1fMB)",
                key,
                len(self._cache),
                self.max_items,
                self._current_memory / (1024 * 1024),
            )
    
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
                self._current_memory -= self._tracked_size(pixmap)
                self._current_tracked_bytes -= self._tracked_bytes_by_key.pop(key, 0)
                self._resource_metadata_by_key.pop(key, None)
                _cache_trace("Removed from cache: %s", key)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached images."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._current_memory = 0
            self._tracked_bytes_by_key.clear()
            self._resource_metadata_by_key.clear()
            self._current_tracked_bytes = 0
            logger.info(f"Cache cleared: {count} images removed")
    
    def size(self) -> int:
        """Get number of cached images."""
        with self._lock:
            return len(self._cache)
    
    def memory_usage(self) -> int:
        """Get exact logical retained image bytes."""
        with self._lock:
            return self._current_memory
    
    def memory_usage_mb(self) -> float:
        """Get exact logical retained image bytes in MiB."""
        with self._lock:
            return self._current_memory / (1024 * 1024)
    
    def tracked_memory_usage(self) -> int:
        """Return exact logical bytes tracked for current cache entries."""
        with self._lock:
            return self._current_tracked_bytes

    def get_accounting_snapshot(self):
        """Return an immutable, detached snapshot of logical cache resources."""
        with self._lock:
            # All Qt-derived metadata is captured by put() on the caller's
            # owning thread. Snapshot readers therefore never touch QPixmap
            # or QImage objects from the background usage sampler.
            resources = [
                self._resource_metadata_by_key[key]
                for key in self._cache
                if key in self._resource_metadata_by_key
            ]
            return MappingProxyType({
                "owner": self._owner,
                "generation": _freeze_snapshot_value(self._generation),
                "total_tracked_bytes": self._current_tracked_bytes,
                "resource_count": len(resources),
                "resources": tuple(resources),
            })

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
                'tracked_memory_bytes': self._current_tracked_bytes,
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
                self._current_tracked_bytes > self.max_memory_bytes)
    
    def _evict_oldest_locked(self) -> None:
        """Evict the least recently used entry (caller holds lock)."""
        if not self._cache:
            return
        key, img = self._cache.popitem(last=False)
        self._current_memory -= self._tracked_size(img)
        self._current_tracked_bytes -= self._tracked_bytes_by_key.pop(key, 0)
        self._resource_metadata_by_key.pop(key, None)
        self._evict_count += 1
        _cache_trace("Evicted from cache: %s", key)
    
    def _estimate_size(self, image: Union[QImage, QPixmap]) -> int:
        """
        Return the legacy RGBA estimate retained only for compatibility.
        
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

    @staticmethod
    def _tracked_size(image: Union[QImage, QPixmap]) -> int:
        """Return exact logical bytes for the supported Qt image type."""
        if image.isNull():
            return 0
        if isinstance(image, QImage):
            return int(image.sizeInBytes())
        bytes_per_pixel = math.ceil(max(0, int(image.depth())) / 8)
        return int(image.width()) * int(image.height()) * bytes_per_pixel

    @staticmethod
    def _image_format(image: Union[QImage, QPixmap]) -> str:
        if isinstance(image, QImage):
            image_format = image.format()
            return getattr(image_format, "name", str(image_format))
        return f"QPixmap(depth={int(image.depth())})"
    
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
