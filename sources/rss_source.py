"""
RSS Feed Image Source

Fetches images from RSS/Atom feeds and caches them locally.
"""
import feedparser
import requests
import hashlib
import tempfile
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse, urlunparse
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
                 timeout_seconds: int = 30,
                 save_to_disk: bool = False,
                 save_directory: Optional[Path] = None,
                 max_images_per_refresh: Optional[int] = None):
        """
        Initialize RSS source.
        
        Args:
            feed_urls: List of RSS/Atom feed URLs (defaults to NASA feeds)
            cache_dir: Directory for cached images (defaults to temp)
            max_cache_size_mb: Maximum cache size in MB
            timeout_seconds: Network timeout in seconds
            save_to_disk: If True, permanently save RSS images to save_directory
            save_directory: Directory for permanent RSS image storage (required if save_to_disk=True)
        """
        self.feed_urls = feed_urls or list(DEFAULT_RSS_FEEDS.values())
        self.timeout = timeout_seconds
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        self.max_images_per_refresh = max_images_per_refresh
        
        # Setup cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup permanent save directory
        self.save_to_disk = save_to_disk
        self.save_directory = None
        if save_to_disk:
            if save_directory:
                self.save_directory = Path(save_directory)
                try:
                    self.save_directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"RSS save-to-disk enabled: {self.save_directory}")
                except Exception as e:
                    logger.error(f"Failed to create RSS save directory: {e}")
                    self.save_to_disk = False
            else:
                logger.warning("RSS save-to-disk enabled but no directory specified, disabling feature")
                self.save_to_disk = False
        
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
    
    def _get_per_feed_image_limit(self) -> Optional[int]:
        try:
            if self.max_images_per_refresh is None:
                return None
            value = int(self.max_images_per_refresh)
            # Negative values are treated as "no limit"; zero is a
            # valid hard limit (skip this feed for the current pass).
            if value < 0:
                return None
            return value
        except Exception:
            return None

    def _resolve_feed_mode(self, feed_url: str) -> tuple[str, str, str]:
        parsed = urlparse(feed_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        path = parsed.path or "/"
        query = parsed.query

        if not netloc and path:
            # Handle inputs like "reddit.com/..." without scheme
            parts = path.split("/", 1)
            candidate_host = parts[0]
            rest = "/" + parts[1] if len(parts) > 1 else "/"
            if "." in candidate_host:
                netloc = candidate_host
                path = rest or "/"

        rebuilt = urlunparse((scheme, netloc, path, "", query, ""))

        lowered_netloc = (netloc or "").lower()
        lowered_path = path.lower()

        if lowered_path.endswith(".json"):
            return rebuilt, "json", feed_url

        if "reddit.com" in lowered_netloc and ".rss" in lowered_path:
            json_path = lowered_path.replace(".rss", ".json")
            json_url = urlunparse((scheme, netloc, json_path, "", query, ""))
            return json_url, "json", feed_url

        return rebuilt, "rss", feed_url

    def _parse_feed(self, feed_url: str) -> None:
        """
        Parse a single RSS/Atom feed and extract images.
        
        Args:
            feed_url: URL of the feed to parse
        """
        logger.debug(f"Parsing feed: {feed_url}")

        request_url, mode, original_url = self._resolve_feed_mode(feed_url)

        if mode == "json":
            self._parse_json_feed(request_url, original_url)
            return

        try:
            feed = feedparser.parse(request_url, request_headers={
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

            limit = self._get_per_feed_image_limit()
            added = 0

            for entry in feed.entries:
                if limit is not None and added >= limit:
                    break
                try:
                    if self._process_entry(entry, feed_url, feed_title):
                        added += 1
                except Exception as e:
                    logger.warning(f"Failed to process entry: {e}")
        
        except Exception as e:
            logger.error(f"Failed to fetch feed {feed_url}: {e}", exc_info=True)
            raise
    
    def _parse_json_feed(self, request_url: str, original_url: str) -> None:
        logger.debug(f"Parsing JSON feed: {request_url}")

        try:
            response = requests.get(
                request_url,
                timeout=self.timeout,
                headers={'User-Agent': 'ShittyRandomPhotoScreenSaver/1.0', 'Accept': 'application/json'},
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch JSON feed {request_url}: {e}")
            return

        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Failed to decode JSON feed {request_url}: {e}")
            return

        entries = []
        try:
            if isinstance(data, dict) and data.get('kind') == 'Listing':
                entries = [c.get('data', {}) for c in data.get('data', {}).get('children', []) if isinstance(c, dict)]
        except Exception:
            entries = []

        feed_title = f"JSON Feed ({original_url})"
        self._feed_data[original_url] = {
            'title': feed_title,
            'updated': '',
            'entries_count': len(entries),
        }

        logger.info(f"JSON feed '{feed_title}': {len(entries)} entries")

        limit = self._get_per_feed_image_limit()
        added = 0

        for post in entries:
            if limit is not None and added >= limit:
                break
            try:
                if self._process_reddit_json_entry(post, original_url, feed_title):
                    added += 1
            except Exception as e:
                logger.warning(f"Failed to process JSON entry: {e}")

    def _process_entry(self, entry, feed_url: str, feed_title: str) -> bool:
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
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
                if img_match:
                    image_url = img_match.group(1)
        
        # Check for thumbnail
        if not image_url and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            image_url = entry.media_thumbnail[0].get('url')
        
        if not image_url:
            logger.debug(f"No image found in entry: {entry.get('title', 'Untitled')}")
            return False
        
        # Download and cache image
        try:
            cached_path = self._download_image(image_url, entry)

            if cached_path:
                metadata = ImageMetadata(
                    source_type=ImageSourceType.RSS,
                    source_id=feed_url,
                    image_id=image_url.split('/')[-1],
                    local_path=cached_path,
                    url=image_url,
                    title=entry.get('title', 'Untitled'),
                    description=entry.get('summary', '')[:500],
                    author=entry.get('author', feed_title),
                    created_date=self._parse_date(entry),
                    fetched_date=datetime.utcnow(),
                    file_size=cached_path.stat().st_size if cached_path.exists() else 0,
                    format=cached_path.suffix[1:].upper() if cached_path.suffix else 'UNKNOWN',
                )

                self._images.append(metadata)
                logger.debug(f"Added image: {metadata.title}")
                return True

        except Exception as e:
            logger.warning(f"Failed to download image from {image_url}: {e}")

        return False

    def _process_reddit_json_entry(self, post: dict, feed_url: str, feed_title: str) -> bool:
        if not isinstance(post, dict):
            return False

        image_url = post.get('url_overridden_by_dest') or post.get('url')
        if not image_url:
            return False

        try:
            parsed = urlparse(image_url)
            path = parsed.path or ""
            lowered = path.lower()
            if not any(lowered.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                return False
        except Exception:
            return False

        # Light high-resolution filter: when Reddit provides preview
        # metadata, prefer images that are at least 2560px wide. If we
        # cannot determine a width, we keep the post (no strict filter).
        min_width = 2560
        try:
            preview = post.get('preview') or {}
            images = preview.get('images') or []
            max_width = None
            if images:
                info = images[0] or {}
                src = info.get('source') or {}
                w = src.get('width')
                if isinstance(w, (int, float)):
                    max_width = int(w)
                for res in info.get('resolutions') or []:
                    rw = res.get('width')
                    if isinstance(rw, (int, float)):
                        rw_i = int(rw)
                        if max_width is None or rw_i > max_width:
                            max_width = rw_i
            if max_width is not None and max_width < min_width:
                return False
        except Exception:
            # If anything goes wrong while reading preview metadata,
            # fall back to accepting the post (light filter only).
            pass

        try:
            cached_path = self._download_image(image_url, post)
            if not cached_path:
                return False

            created_ts = post.get('created_utc')
            created_date = None
            try:
                if isinstance(created_ts, (int, float)):
                    created_date = datetime.utcfromtimestamp(created_ts)
            except Exception:
                created_date = None

            metadata = ImageMetadata(
                source_type=ImageSourceType.RSS,
                source_id=feed_url,
                image_id=image_url.split('/')[-1],
                local_path=cached_path,
                url=image_url,
                title=post.get('title', 'Untitled'),
                description=(post.get('selftext') or "")[:500],
                author=post.get('author', feed_title),
                created_date=created_date,
                fetched_date=datetime.utcnow(),
                file_size=cached_path.stat().st_size if cached_path.exists() else 0,
                format=cached_path.suffix[1:].upper() if cached_path.suffix else 'UNKNOWN',
            )

            self._images.append(metadata)
            logger.debug(f"Added JSON image: {metadata.title}")
            return True

        except Exception as e:
            logger.warning(f"Failed to download JSON image from {image_url}: {e}")
            return False
    
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
            
            # Optionally save to permanent storage
            if self.save_to_disk and self.save_directory:
                try:
                    save_file = self.save_directory / cache_file.name
                    if not save_file.exists():
                        shutil.copy2(cache_file, save_file)
                        logger.info(f"Saved RSS image to disk: {save_file}")
                except Exception as e:
                    logger.warning(f"Failed to save RSS image to disk: {e}")
            
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
