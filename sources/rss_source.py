"""
RSS Feed Image Source

Fetches images from RSS/Atom feeds and caches them locally.
"""
import feedparser
import requests
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
from sources.base_provider import ImageProvider, ImageMetadata, ImageSourceType
from core.logging.logger import get_logger

logger = get_logger(__name__)


# Default safe RSS feeds with images
DEFAULT_RSS_FEEDS = {
    "NASA Image of the Day": "https://www.nasa.gov/feeds/iotd-feed",
    "Wikimedia Picture of the Day": "https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=potd&feedformat=rss&language=en",
    "NASA Breaking News": "https://www.nasa.gov/news-release/feed/",
}


class RSSSource(ImageProvider):
    """
    RSS feed-based image provider.
    
    Features:
    - Parses RSS/Atom feeds for images
    - Downloads and caches images locally
    - Supports multiple feeds simultaneously
    - Automatic cache management
    - Graceful error handling
    """
    
    def __init__(self, feed_urls: Optional[List[str]] = None, 
                 cache_dir: Optional[Path] = None,
                 max_cache_size_mb: int = 500,
                 timeout_seconds: int = 30):
        """
        Initialize RSS source.
        
        Args:
            feed_urls: List of RSS/Atom feed URLs (defaults to NASA feeds)
            cache_dir: Directory for cached images (defaults to temp)
            max_cache_size_mb: Maximum cache size in MB
            timeout_seconds: Network timeout in seconds
        """
        self.feed_urls = feed_urls or list(DEFAULT_RSS_FEEDS.values())
        self.timeout = timeout_seconds
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        
        # Setup cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._images: List[ImageMetadata] = []
        self._feed_data = {}  # Store feed metadata
        
        logger.info(f"RSSSource initialized with {len(self.feed_urls)} feeds")
        logger.info(f"Cache directory: {self.cache_dir}")
    
    def get_images(self) -> List[ImageMetadata]:
        """Get all images from RSS feeds."""
        if not self._images:
            self.refresh()
        return self._images.copy()
    
    def refresh(self) -> None:
        """Refresh images from all RSS feeds."""
        logger.info("Refreshing RSS feeds...")
        self._images.clear()
        
        for feed_url in self.feed_urls:
            try:
                self._parse_feed(feed_url)
            except Exception as e:
                logger.error(f"[FALLBACK] Failed to parse feed {feed_url}: {e}")
                # Continue with other feeds (fallback behavior)
        
        logger.info(f"RSS refresh complete: {len(self._images)} images found")
        
        # Cleanup old cache if needed
        self._cleanup_cache()
    
    def _parse_feed(self, feed_url: str) -> None:
        """
        Parse a single RSS/Atom feed and extract images.
        
        Args:
            feed_url: URL of the feed to parse
        """
        logger.debug(f"Parsing feed: {feed_url}")
        
        try:
            # Parse feed
            feed = feedparser.parse(feed_url, request_headers={
                'User-Agent': 'ShittyRandomPhotoScreenSaver/1.0'
            })
            
            if feed.bozo:
                # Feed has parsing errors but may still be usable
                logger.warning(f"[FALLBACK] Feed has parsing errors: {feed_url}")
                logger.warning(f"Bozo exception: {feed.get('bozo_exception', 'Unknown')}")
            
            # Store feed metadata
            feed_title = feed.feed.get('title', 'Unknown Feed')
            self._feed_data[feed_url] = {
                'title': feed_title,
                'updated': feed.feed.get('updated', ''),
                'entries_count': len(feed.entries)
            }
            
            logger.info(f"Feed '{feed_title}': {len(feed.entries)} entries")
            
            # Process each entry
            for entry in feed.entries:
                try:
                    self._process_entry(entry, feed_url, feed_title)
                except Exception as e:
                    logger.warning(f"Failed to process entry: {e}")
                    # Continue with other entries
        
        except Exception as e:
            logger.error(f"Failed to fetch feed {feed_url}: {e}", exc_info=True)
            raise
    
    def _process_entry(self, entry, feed_url: str, feed_title: str) -> None:
        """
        Process a single feed entry and extract image.
        
        Args:
            entry: Feed entry from feedparser
            feed_url: URL of the parent feed
            feed_title: Title of the parent feed
        """
        # Try to find image URL from various fields
        image_url = None
        
        # Check media:content (common in RSS 2.0)
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('medium') == 'image' or 'image' in media.get('type', ''):
                    image_url = media.get('url')
                    break
        
        # Check enclosures (podcast-style)
        if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if 'image' in enclosure.get('type', ''):
                    image_url = enclosure.get('href')
                    break
        
        # Check content/summary for img tags
        if not image_url:
            content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
            if content:
                # Simple img src extraction
                import re
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
                if img_match:
                    image_url = img_match.group(1)
        
        # Check for thumbnail
        if not image_url and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            image_url = entry.media_thumbnail[0].get('url')
        
        if not image_url:
            logger.debug(f"No image found in entry: {entry.get('title', 'Untitled')}")
            return
        
        # Download and cache image
        try:
            cached_path = self._download_image(image_url, entry)
            
            if cached_path:
                # Create metadata
                metadata = ImageMetadata(
                    source_type=ImageSourceType.RSS,
                    source_identifier=feed_url,
                    path=str(cached_path),
                    url=image_url,
                    title=entry.get('title', 'Untitled'),
                    description=entry.get('summary', '')[:500],  # Limit description length
                    author=entry.get('author', feed_title),
                    published_date=self._parse_date(entry),
                    file_size=cached_path.stat().st_size if cached_path.exists() else 0,
                    format=cached_path.suffix[1:].upper() if cached_path.suffix else 'UNKNOWN'
                )
                
                self._images.append(metadata)
                logger.debug(f"Added image: {metadata.title}")
        
        except Exception as e:
            logger.warning(f"Failed to download image from {image_url}: {e}")
    
    def _download_image(self, image_url: str, entry) -> Optional[Path]:
        """
        Download and cache an image.
        
        Args:
            image_url: URL of the image to download
            entry: Feed entry (for generating cache filename)
        
        Returns:
            Path to cached image, or None if download failed
        """
        # Generate cache filename from URL hash
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        
        # Try to determine extension from URL
        parsed = urlparse(image_url)
        ext = Path(parsed.path).suffix or '.jpg'
        
        cache_file = self.cache_dir / f"{url_hash}{ext}"
        
        # Return cached file if exists
        if cache_file.exists():
            logger.debug(f"Using cached image: {cache_file.name}")
            return cache_file
        
        # Download image
        logger.debug(f"Downloading image: {image_url}")
        
        try:
            response = requests.get(
                image_url,
                timeout=self.timeout,
                headers={'User-Agent': 'ShittyRandomPhotoScreenSaver/1.0'},
                stream=True
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                logger.warning(f"URL does not point to an image: {content_type}")
                return None
            
            # Write to cache
            with open(cache_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded image: {cache_file.name} ({cache_file.stat().st_size} bytes)")
            return cache_file
        
        except requests.RequestException as e:
            logger.error(f"Download failed for {image_url}: {e}")
            return None
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """
        Parse date from feed entry.
        
        Args:
            entry: Feed entry
        
        Returns:
            Parsed datetime or None
        """
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except Exception:
                        pass
        
        return None
    
    def _cleanup_cache(self) -> None:
        """Clean up cache if it exceeds max size."""
        try:
            # Get all cached files with their modification times
            cache_files = []
            total_size = 0
            
            for file in self.cache_dir.glob('*'):
                if file.is_file():
                    size = file.stat().st_size
                    mtime = file.stat().st_mtime
                    cache_files.append((file, size, mtime))
                    total_size += size
            
            if total_size <= self.max_cache_size:
                logger.debug(f"Cache size OK: {total_size / 1024 / 1024:.1f}MB")
                return
            
            logger.info(f"[FALLBACK] Cache size exceeded ({total_size / 1024 / 1024:.1f}MB), cleaning up...")
            
            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[2])
            
            # Remove oldest files until under limit
            removed_count = 0
            removed_size = 0
            
            for file, size, _ in cache_files:
                if total_size - removed_size <= self.max_cache_size * 0.8:  # 80% threshold
                    break
                
                try:
                    file.unlink()
                    removed_count += 1
                    removed_size += size
                    logger.debug(f"Removed cached file: {file.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove {file}: {e}")
            
            logger.info(f"Cache cleanup: removed {removed_count} files ({removed_size / 1024 / 1024:.1f}MB)")
        
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def is_available(self) -> bool:
        """Check if RSS source is available (has valid feeds)."""
        return len(self.feed_urls) > 0
    
    def get_source_info(self) -> dict:
        """Get source information."""
        return {
            'type': 'RSS Feed',
            'feeds': len(self.feed_urls),
            'cached_images': len(self._images),
            'cache_directory': str(self.cache_dir),
            'feed_data': self._feed_data
        }
    
    def add_feed(self, feed_url: str) -> None:
        """
        Add a new RSS feed.
        
        Args:
            feed_url: URL of the RSS/Atom feed
        """
        if feed_url not in self.feed_urls:
            self.feed_urls.append(feed_url)
            logger.info(f"Added feed: {feed_url}")
    
    def remove_feed(self, feed_url: str) -> bool:
        """
        Remove an RSS feed.
        
        Args:
            feed_url: URL of the feed to remove
        
        Returns:
            True if removed, False if not found
        """
        if feed_url in self.feed_urls:
            self.feed_urls.remove(feed_url)
            logger.info(f"Removed feed: {feed_url}")
            return True
        return False
    
    def clear_cache(self) -> int:
        """
        Clear all cached images.
        
        Returns:
            Number of files removed
        """
        removed_count = 0
        
        try:
            for file in self.cache_dir.glob('*'):
                if file.is_file():
                    file.unlink()
                    removed_count += 1
            
            logger.info(f"Cache cleared: {removed_count} files removed")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
        
        return removed_count
