"""Imgur Image Cache Module.

Manages disk caching of downloaded Imgur images with LRU eviction.
Provides thread-safe access to cached images.

Thread Safety:
- All cache operations use threading.Lock()
- Cache metadata stored in JSON for persistence
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

from core.logging.logger import get_logger
from core.settings.storage_paths import get_imgur_cache_dir

logger = get_logger(__name__)

# Cache configuration
DEFAULT_CACHE_DIR = get_imgur_cache_dir()
MAX_CACHE_SIZE_MB = 100
MAX_CACHE_ITEMS = 500
CACHE_METADATA_FILE = "cache_metadata.json"

# Image processing
MAX_IMAGE_DIMENSION = 1024  # Max dimension for cached images
THUMBNAIL_SIZE = 600  # Max dimension for thumbnails (fast loading, good quality)


@dataclass
class CachedImage:
    """Metadata for a cached image."""
    id: str
    path: str
    size_bytes: int
    width: int
    height: int
    last_accessed: float
    download_time: float
    is_animated: bool = False
    gallery_url: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "CachedImage":
        return cls(**data)


class ImgurImageCache:
    """Thread-safe disk cache for Imgur images.
    
    Features:
    - LRU eviction when cache size exceeds limit
    - Persistent metadata for fast startup
    - Image resizing on cache
    - Aspect ratio tracking for layout
    
    Thread Safety:
        All public methods are thread-safe via _lock.
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_size_mb: int = MAX_CACHE_SIZE_MB,
        max_items: int = MAX_CACHE_ITEMS,
    ) -> None:
        """Initialize the image cache.
        
        Args:
            cache_dir: Directory for cached images
            max_size_mb: Maximum cache size in MB
            max_items: Maximum number of cached items
        """
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._max_items = max_items
        self._lock = threading.Lock()
        
        # In-memory cache metadata
        self._cache: Dict[str, CachedImage] = {}
        self._total_size_bytes: int = 0
        
        # Ensure cache directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing metadata
        self._load_metadata()
        
        logger.debug("[IMGUR_CACHE] Initialized with %d items, %d MB",
                    len(self._cache), self._total_size_bytes // (1024 * 1024))
    
    @property
    def cache_dir(self) -> Path:
        """Get the cache directory path."""
        return self._cache_dir
    
    def _metadata_path(self) -> Path:
        """Get path to metadata file."""
        return self._cache_dir / CACHE_METADATA_FILE
    
    def _load_metadata(self) -> None:
        """Load cache metadata from disk, rebuilding from files if needed."""
        meta_path = self._metadata_path()
        
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self._total_size_bytes = 0
                for item_data in data.get("items", []):
                    try:
                        cached = CachedImage.from_dict(item_data)
                        # Verify file still exists
                        if Path(cached.path).exists():
                            self._cache[cached.id] = cached
                            self._total_size_bytes += cached.size_bytes
                    except Exception as e:
                        logger.debug("[IMGUR_CACHE] Failed to load cache item: %s", e)
                
                logger.debug("[IMGUR_CACHE] Loaded %d cached items from metadata", len(self._cache))
                return
                
            except Exception as e:
                logger.warning("[IMGUR_CACHE] Failed to load metadata: %s", e)
        
        # Rebuild from existing files if metadata missing/corrupt
        self._rebuild_from_files()
    
    def _rebuild_from_files(self) -> None:
        """Rebuild cache metadata from existing image files in cache directory."""
        if not self._cache_dir.exists():
            return
        
        rebuilt_count = 0
        for path in self._cache_dir.glob("*.jpg"):
            try:
                image_id = path.stem
                if image_id in self._cache:
                    continue
                
                size_bytes = path.stat().st_size
                if size_bytes < 100:  # Skip corrupt/empty files
                    continue
                
                # Try to get dimensions from image
                width, height = 160, 160
                try:
                    img = QImage(str(path))
                    if not img.isNull():
                        width = img.width()
                        height = img.height()
                except Exception:
                    pass
                
                now = time.time()
                cached = CachedImage(
                    id=image_id,
                    path=str(path),
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    last_accessed=now,
                    download_time=path.stat().st_mtime,
                    is_animated=False,
                    gallery_url=f"https://imgur.com/gallery/{image_id}",
                )
                
                self._cache[image_id] = cached
                self._total_size_bytes += size_bytes
                rebuilt_count += 1
                
            except Exception as e:
                logger.debug("[IMGUR_CACHE] Failed to rebuild from %s: %s", path.name, e)
        
        if rebuilt_count > 0:
            logger.info("[IMGUR_CACHE] Rebuilt %d items from existing files", rebuilt_count)
            self._save_metadata()
    
    def _save_metadata(self) -> None:
        """Save cache metadata to disk."""
        try:
            data = {
                "version": 1,
                "items": [item.to_dict() for item in self._cache.values()],
                "total_size_bytes": self._total_size_bytes,
                "saved_at": datetime.now().isoformat(),
            }
            
            meta_path = self._metadata_path()
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.warning("[IMGUR_CACHE] Failed to save metadata: %s", e)
    
    def _get_image_path(self, image_id: str, extension: str = "jpg") -> Path:
        """Get the path for a cached image."""
        return self._cache_dir / f"{image_id}.{extension}"
    
    
    def _evict_lru(self, needed_bytes: int = 0) -> None:
        """Evict least recently used items to make space.
        
        Args:
            needed_bytes: Additional bytes needed for new item
        """
        # Sort by last_accessed (oldest first)
        items = sorted(self._cache.values(), key=lambda x: x.last_accessed)
        
        target_size = self._max_size_bytes - needed_bytes
        evicted_count = 0
        
        while (self._total_size_bytes > target_size or len(self._cache) >= self._max_items) and items:
            item = items.pop(0)
            
            # Remove file and thumbnail
            try:
                path = Path(item.path)
                if path.exists():
                    path.unlink()
                # Also delete thumbnail if exists
                if item.thumbnail_path:
                    thumb_path = Path(item.thumbnail_path)
                    if thumb_path.exists():
                        thumb_path.unlink()
            except Exception as e:
                logger.debug("[IMGUR_CACHE] Failed to delete %s: %s", item.id, e)
            
            # Remove from cache
            self._total_size_bytes -= item.size_bytes
            del self._cache[item.id]
            evicted_count += 1
        
        if evicted_count > 0:
            logger.debug("[IMGUR_CACHE] Evicted %d items (LRU)", evicted_count)
    
    def has(self, image_id: str) -> bool:
        """Check if an image is in the cache."""
        with self._lock:
            return image_id in self._cache
    
    
    def get(self, image_id: str) -> Optional[Tuple[Path, CachedImage]]:
        """Get a cached image path and metadata.
        
        Updates last_accessed time for LRU tracking.
        
        Returns:
            Tuple of (path, metadata) or None if not cached
        """
        with self._lock:
            if image_id not in self._cache:
                return None
            
            cached = self._cache[image_id]
            path = Path(cached.path)
            
            if not path.exists():
                # File was deleted externally
                del self._cache[image_id]
                self._total_size_bytes -= cached.size_bytes
                return None
            
            # Update access time
            cached.last_accessed = time.time()
            
            return (path, cached)
    
    def get_pixmap(self, image_id: str, max_size: Optional[Tuple[int, int]] = None, use_thumbnail: bool = True) -> Optional[QPixmap]:
        """Get a cached image as QPixmap.
        
        Args:
            image_id: Image ID
            max_size: Optional (width, height) to scale to
            use_thumbnail: IGNORED - always use full resolution for quality
            
        Returns:
            QPixmap or None if not cached
        """
        result = self.get(image_id)
        if result is None:
            return None
        
        path, cached = result
        
        try:
            # ALWAYS use full resolution image for quality (thumbnails cause blur)
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return None
            
            # Set DPR to 1.0 so the widget's paint cache can handle DPR scaling properly
            # This prevents double-scaling issues
            try:
                pixmap.setDevicePixelRatio(1.0)
            except Exception:
                pass
            
            return pixmap
            
        except Exception as e:
            logger.debug("[IMGUR_CACHE] Failed to load pixmap %s: %s", image_id, e)
            return None
    
    def put(
        self,
        image_id: str,
        image_data: bytes,
        extension: str = "jpg",
        is_animated: bool = False,
        gallery_url: str = "",
    ) -> Optional[CachedImage]:
        """Add an image to the cache.
        
        Resizes large images and handles cache eviction.
        
        Args:
            image_id: Unique image ID
            image_data: Raw image bytes
            extension: File extension (jpg, png, gif)
            is_animated: Whether image is animated
            gallery_url: URL to Imgur gallery
            
        Returns:
            CachedImage metadata or None on failure
        """
        with self._lock:
            # Check if already cached
            if image_id in self._cache:
                return self._cache[image_id]
            
            # Evict if needed
            if len(image_data) + self._total_size_bytes > self._max_size_bytes:
                self._evict_lru(len(image_data))
            
            if len(self._cache) >= self._max_items:
                self._evict_lru()
            
            # Save to disk
            path = self._get_image_path(image_id, extension)
            
            try:
                # Handle animated GIFs - extract first frame
                if is_animated or extension.lower() == "gif":
                    try:
                        from PIL import Image
                        import io
                        
                        pil_img = Image.open(io.BytesIO(image_data))
                        # Seek to first frame
                        pil_img.seek(0)
                        # Convert to RGB if necessary (GIFs may have palette)
                        if pil_img.mode != 'RGB':
                            pil_img = pil_img.convert('RGB')
                        # Save as JPEG for efficiency
                        path = self._get_image_path(image_id, "jpg")
                        pil_img.save(str(path), 'JPEG', quality=85)
                        extension = "jpg"
                        logger.debug("[IMGUR_CACHE] Converted GIF %s to first frame JPEG", image_id)
                    except Exception as e:
                        logger.debug("[IMGUR_CACHE] GIF conversion failed, saving as-is: %s", e)
                        with open(path, "wb") as f:
                            f.write(image_data)
                else:
                    with open(path, "wb") as f:
                        f.write(image_data)
                
                # Get image dimensions (no thumbnail generation)
                width, height = 0, 0
                try:
                    img = QImage(str(path))
                    if not img.isNull():
                        width = img.width()
                        height = img.height()
                        
                        # Resize if too large
                        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                            img = img.scaled(
                                MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                            img.save(str(path))
                            width = img.width()
                            height = img.height()
                except Exception as e:
                    logger.debug("[IMGUR_CACHE] Failed to process image dimensions: %s", e)
                
                # Get final file size
                size_bytes = path.stat().st_size
                
                # Create metadata (no thumbnail_path)
                now = time.time()
                cached = CachedImage(
                    id=image_id,
                    path=str(path),
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    last_accessed=now,
                    download_time=now,
                    is_animated=is_animated,
                    gallery_url=gallery_url,
                )
                
                self._cache[image_id] = cached
                self._total_size_bytes += size_bytes
                
                # Save metadata after every cache operation for persistence
                self._save_metadata()
                
                logger.debug("[IMGUR_CACHE] Cached %s (%dx%d, %d KB)",
                           image_id, width, height, size_bytes // 1024)
                
                return cached
                
            except Exception as e:
                logger.error("[IMGUR_CACHE] Failed to cache %s: %s", image_id, e)
                # Clean up partial file
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass
                return None
    
    def get_all_cached(self) -> List[CachedImage]:
        """Get all cached image metadata, sorted by last_accessed (newest first)."""
        with self._lock:
            return sorted(
                self._cache.values(),
                key=lambda x: x.last_accessed,
                reverse=True,
            )
    
    def get_cached_count(self) -> int:
        """Get number of cached images."""
        with self._lock:
            return len(self._cache)
    
    def get_cache_size_mb(self) -> float:
        """Get current cache size in MB."""
        with self._lock:
            return self._total_size_bytes / (1024 * 1024)
    
    def clear(self) -> None:
        """Clear all cached images."""
        with self._lock:
            # Delete all files
            for cached in self._cache.values():
                try:
                    path = Path(cached.path)
                    if path.exists():
                        path.unlink()
                except Exception as e:
                    logger.debug("[IMGUR_CACHE] Failed to delete %s: %s", cached.id, e)
            
            self._cache.clear()
            self._total_size_bytes = 0
            
            # Delete metadata
            try:
                meta_path = self._metadata_path()
                if meta_path.exists():
                    meta_path.unlink()
            except Exception:
                pass
            
            logger.info("[IMGUR_CACHE] Cache cleared")
    
    def save(self) -> None:
        """Save cache metadata to disk."""
        with self._lock:
            self._save_metadata()
    
    def cleanup(self) -> None:
        """Clean up and save cache before shutdown."""
        self.save()
        logger.debug("[IMGUR_CACHE] Cleanup complete")
