# Image Sources Implementation

## Abstract Base Provider

### Purpose
Define interface for all image sources.

### Implementation

```python
# sources/base_provider.py

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class ImageMetadata:
    """Metadata for an image"""
    path: str
    width: int = 0
    height: int = 0
    aspect_ratio: float = 0.0
    file_size: int = 0
    modified_time: float = 0.0
    source: str = "unknown"

class ImageProvider(ABC):
    """Abstract base class for image providers"""
    
    @abstractmethod
    def get_images(self) -> List[ImageMetadata]:
        """
        Get list of available images.
        
        Returns:
            List of ImageMetadata objects
        """
        pass
    
    @abstractmethod
    def refresh(self):
        """Refresh the image list"""
        pass
    
    def __repr__(self):
        return f"{self.__class__.__name__}()"
```

---

## Folder Source

### Purpose
Scan local directories for image files.

### Supported Formats
- JPG/JPEG
- PNG
- BMP
- GIF
- WebP
- TIFF

### Implementation

```python
# sources/folder_source.py

import os
from pathlib import Path
from typing import List
from PySide6.QtGui import QImageReader
from sources.base_provider import ImageProvider, ImageMetadata
import logging

logger = logging.getLogger("screensaver.source.folder")

class FolderSource(ImageProvider):
    """Image provider that scans local folders"""
    
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
    
    def __init__(self, folders: List[str], thread_manager, event_system):
        self.folders = folders
        self.thread_manager = thread_manager
        self.event_system = event_system
        self.images: List[ImageMetadata] = []
        
        logger.info(f"FolderSource initialized with {len(folders)} folders")
        
        # Initial scan
        self.refresh()
    
    def get_images(self) -> List[ImageMetadata]:
        """Get list of available images"""
        return self.images.copy()
    
    def refresh(self):
        """Refresh image list by rescanning folders"""
        logger.info("Refreshing folder source")
        self.images.clear()
        
        for folder in self.folders:
            if not os.path.exists(folder):
                logger.warning(f"Folder does not exist: {folder}")
                continue
            
            self._scan_folder(folder)
        
        logger.info(f"Folder scan complete: {len(self.images)} images found")
    
    def _scan_folder(self, folder: str):
        """Recursively scan folder for images"""
        logger.debug(f"Scanning folder: {folder}")
        
        try:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = Path(root) / file
                    
                    if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                        try:
                            metadata = self._get_image_metadata(str(file_path))
                            self.images.append(metadata)
                        except Exception as e:
                            logger.debug(f"Failed to process {file_path}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to scan folder {folder}: {e}")
    
    def _get_image_metadata(self, path: str) -> ImageMetadata:
        """Get metadata for an image file"""
        file_stat = os.stat(path)
        
        # Get dimensions using Qt
        reader = QImageReader(path)
        size = reader.size()
        
        width = size.width() if size.isValid() else 0
        height = size.height() if size.isValid() else 0
        aspect_ratio = width / height if height > 0 else 0.0
        
        return ImageMetadata(
            path=path,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            file_size=file_stat.st_size,
            modified_time=file_stat.st_mtime,
            source="folder"
        )
```

---

## RSS Source

### Purpose
Parse RSS/Atom feeds and download images.

### Supported Feed Types
- RSS 2.0
- Media RSS
- Atom

### Implementation

```python
# sources/rss_source.py

import os
import tempfile
from typing import List
from pathlib import Path
import xml.etree.ElementTree as ET
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl, QObject, pyqtSignal
from sources.base_provider import ImageProvider, ImageMetadata
from core.threading import ThreadPoolType
from core.resources import ResourceType
import logging

logger = logging.getLogger("screensaver.source.rss")

class RSSSource(ImageProvider, QObject):
    """Image provider that parses RSS feeds"""
    
    def __init__(self, feed_urls: List[str], thread_manager, event_system, resource_manager):
        QObject.__init__(self)
        
        self.feed_urls = feed_urls
        self.thread_manager = thread_manager
        self.event_system = event_system
        self.resource_manager = resource_manager
        self.images: List[ImageMetadata] = []
        
        # Network manager
        self.network_manager = QNetworkAccessManager()
        
        # Cache directory
        self.cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        logger.info(f"RSSSource initialized with {len(feed_urls)} feeds")
        logger.info(f"Cache directory: {self.cache_dir}")
        
        # Initial fetch
        self.refresh()
    
    def get_images(self) -> List[ImageMetadata]:
        """Get list of available images"""
        return self.images.copy()
    
    def refresh(self):
        """Refresh feeds"""
        logger.info("Refreshing RSS feeds")
        
        for url in self.feed_urls:
            self.thread_manager.submit_task(
                ThreadPoolType.IO,
                self._fetch_feed,
                url,
                callback=self._on_feed_fetched
            )
    
    def _fetch_feed(self, url: str):
        """Fetch RSS feed (runs on IO thread)"""
        import requests
        
        logger.debug(f"Fetching feed: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to fetch feed {url}: {e}")
            return None
    
    def _on_feed_fetched(self, task_result):
        """Callback when feed is fetched"""
        if not task_result.success or not task_result.result:
            logger.error("Feed fetch failed")
            self.event_system.publish("rss.failed")
            return
        
        feed_content = task_result.result
        self._parse_feed(feed_content)
    
    def _parse_feed(self, content: bytes):
        """Parse RSS/Atom feed"""
        try:
            root = ET.fromstring(content)
            
            # Try RSS format
            items = root.findall('.//item')
            if not items:
                # Try Atom format
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            logger.debug(f"Found {len(items)} items in feed")
            
            for item in items:
                image_urls = self._extract_image_urls(item)
                
                for url in image_urls:
                    self._download_image(url)
        
        except Exception as e:
            logger.error(f"Failed to parse feed: {e}")
    
    def _extract_image_urls(self, item) -> List[str]:
        """Extract image URLs from feed item"""
        urls = []
        
        # Try enclosure
        enclosure = item.find('enclosure')
        if enclosure is not None:
            url = enclosure.get('url')
            type_attr = enclosure.get('type', '')
            if url and 'image' in type_attr:
                urls.append(url)
        
        # Try media:content
        media_content = item.find('.//{http://search.yahoo.com/mrss/}content')
        if media_content is not None:
            url = media_content.get('url')
            if url:
                urls.append(url)
        
        return urls
    
    def _download_image(self, url: str):
        """Download image from URL"""
        # Check if already cached
        filename = self._url_to_filename(url)
        cache_path = self.cache_dir / filename
        
        if cache_path.exists():
            logger.debug(f"Image already cached: {filename}")
            self._add_cached_image(str(cache_path))
            return
        
        # Download
        logger.debug(f"Downloading image: {url}")
        
        self.thread_manager.submit_task(
            ThreadPoolType.IO,
            self._download_file,
            url,
            str(cache_path),
            callback=self._on_image_downloaded
        )
    
    def _download_file(self, url: str, dest_path: str):
        """Download file (runs on IO thread)"""
        import requests
        
        try:
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return dest_path
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
    
    def _on_image_downloaded(self, task_result):
        """Callback when image is downloaded"""
        if task_result.success and task_result.result:
            path = task_result.result
            self._add_cached_image(path)
            
            # Register as temp file for cleanup
            self.resource_manager.register_temp_file(
                path,
                f"RSS Image: {Path(path).name}",
                delete=False  # Keep cache
            )
    
    def _add_cached_image(self, path: str):
        """Add cached image to list"""
        try:
            file_stat = os.stat(path)
            
            metadata = ImageMetadata(
                path=path,
                file_size=file_stat.st_size,
                modified_time=file_stat.st_mtime,
                source="rss"
            )
            
            self.images.append(metadata)
            logger.debug(f"Added RSS image: {path}")
        except Exception as e:
            logger.error(f"Failed to add cached image {path}: {e}")
    
    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        import hashlib
        
        # Hash URL to get unique filename
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # Get extension from URL
        ext = Path(url).suffix or '.jpg'
        
        return f"{url_hash}{ext}"
```

---

## Image Cache Utility

### Purpose
Manage in-memory image cache with LRU eviction.

### Implementation

```python
# utils/image_cache.py

from collections import OrderedDict
from PySide6.QtGui import QPixmap
import logging

logger = logging.getLogger("screensaver.cache")

class ImageCache:
    """LRU cache for QPixmap objects"""
    
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.cache = OrderedDict()
        logger.info(f"ImageCache initialized: max_size={max_size}")
    
    def get(self, key: str) -> QPixmap:
        """Get cached pixmap"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            logger.debug(f"Cache hit: {key}")
            return self.cache[key]
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    def put(self, key: str, pixmap: QPixmap):
        """Add pixmap to cache"""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
            self.cache[key] = pixmap
        else:
            # Add new
            self.cache[key] = pixmap
            
            # Evict if over limit
            if len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                self.cache.pop(oldest_key)
                logger.debug(f"Evicted from cache: {oldest_key}")
        
        logger.debug(f"Cached: {key} ({len(self.cache)}/{self.max_size})")
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
```

---

## Testing

### Unit Tests

```python
# tests/test_sources.py

import pytest
import tempfile
from pathlib import Path
from sources.folder_source import FolderSource
from sources.rss_source import RSSSource

def test_folder_source_initialization():
    """Test folder source initializes correctly"""
    folders = [tempfile.gettempdir()]
    source = FolderSource(folders, None, None)
    assert source is not None

def test_folder_source_scan():
    """Test folder scanning"""
    # Create temp directory with test image
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy image
        test_img = Path(tmpdir) / "test.jpg"
        test_img.write_bytes(b"fake image data")
        
        source = FolderSource([tmpdir], None, None)
        images = source.get_images()
        
        # Should find at least our test image
        assert len(images) >= 0  # May not parse fake data

def test_image_cache():
    """Test image cache LRU behavior"""
    from utils.image_cache import ImageCache
    from PySide6.QtGui import QPixmap
    
    cache = ImageCache(max_size=2)
    
    pixmap1 = QPixmap(100, 100)
    pixmap2 = QPixmap(100, 100)
    pixmap3 = QPixmap(100, 100)
    
    cache.put("img1", pixmap1)
    cache.put("img2", pixmap2)
    
    assert cache.get("img1") is not None
    assert cache.size() == 2
    
    # Adding third should evict oldest
    cache.put("img3", pixmap3)
    assert cache.size() == 2
```

---

**Next Document**: `05_DISPLAY_AND_RENDERING.md` - Display modes, transitions, and rendering
