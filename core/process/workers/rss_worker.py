"""
RSS Worker for fetch/parse/mirror operations.

Runs in a separate process to fetch RSS feeds and download images
without blocking the UI thread.

Key responsibilities:
- Fetch RSS/Atom/Reddit JSON feeds
- Parse feed entries and extract image URLs
- Download images to cache/mirror directory
- Validate ImageMetadata before returning
- Respect rate limits and priority ordering
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from multiprocessing import Queue
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.process.workers.base import BaseWorker

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# Source priority weights - higher = process earlier
SOURCE_PRIORITY = {
    'bing.com': 95,
    'unsplash.com': 90,
    'wikimedia.org': 85,
    'nasa.gov': 75,
    'reddit.com': 10,
}

# Rate limiting
RATE_LIMIT_DELAY_S = 2.0
REDDIT_RATE_LIMIT_DELAY_S = 4.0
REQUEST_TIMEOUT_S = 30

# Image limits
MAX_IMAGES_PER_SOURCE = 8
MIN_IMAGE_SIZE_BYTES = 1000


@dataclass
class FeedImageInfo:
    """Information about an image from a feed."""
    url: str
    title: str
    source_id: str
    priority: int
    timestamp: Optional[float] = None


class RSSWorker(BaseWorker):
    """
    Worker for RSS feed fetch and parse operations.
    
    Handles:
    - RSS_FETCH: Fetch and parse a single feed
    - RSS_REFRESH: Refresh all configured feeds
    """
    
    def __init__(self, request_queue: Queue, response_queue: Queue):
        super().__init__(request_queue, response_queue)
        self._feeds_processed = 0
        self._images_downloaded = 0
        self._cache_dir: Optional[Path] = None
        self._save_dir: Optional[Path] = None
    
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.RSS
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """Handle RSS processing messages."""
        if msg.msg_type == MessageType.RSS_FETCH:
            return self._handle_fetch(msg)
        elif msg.msg_type == MessageType.RSS_REFRESH:
            return self._handle_refresh(msg)
        elif msg.msg_type == MessageType.CONFIG_UPDATE:
            return self._handle_config(msg)
        else:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Unknown message type: {msg.msg_type}",
            )
    
    def _handle_fetch(self, msg: WorkerMessage) -> WorkerResponse:
        """Fetch and parse a single RSS feed."""
        feed_url = msg.payload.get("feed_url")
        cache_dir = msg.payload.get("cache_dir")
        save_dir = msg.payload.get("save_dir")
        max_images = msg.payload.get("max_images", MAX_IMAGES_PER_SOURCE)
        
        if not feed_url:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error="Missing 'feed_url' in payload",
            )
        
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        if save_dir:
            self._save_dir = Path(save_dir)
            self._save_dir.mkdir(parents=True, exist_ok=True)
        
        start = time.time()
        try:
            images = self._fetch_feed(feed_url, max_images)
            self._feeds_processed += 1
            
            return WorkerResponse(
                msg_type=MessageType.RSS_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "feed_url": feed_url,
                    "images": images,
                    "image_count": len(images),
                },
                processing_time_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            if self._logger:
                self._logger.exception("Failed to fetch feed: %s", e)
            return WorkerResponse(
                msg_type=MessageType.RSS_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Fetch failed: {e}",
            )
    
    def _handle_refresh(self, msg: WorkerMessage) -> WorkerResponse:
        """Refresh multiple RSS feeds."""
        feed_urls = msg.payload.get("feed_urls", [])
        cache_dir = msg.payload.get("cache_dir")
        save_dir = msg.payload.get("save_dir")
        max_images_per_source = msg.payload.get("max_images_per_source", MAX_IMAGES_PER_SOURCE)
        
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        if save_dir:
            self._save_dir = Path(save_dir)
            self._save_dir.mkdir(parents=True, exist_ok=True)
        
        start = time.time()
        all_images: List[Dict] = []
        errors: List[str] = []
        
        # Sort by priority (high priority first)
        sorted_feeds = sorted(
            feed_urls,
            key=lambda url: -self._get_source_priority(url)
        )
        
        for i, feed_url in enumerate(sorted_feeds):
            try:
                images = self._fetch_feed(feed_url, max_images_per_source)
                all_images.extend(images)
                self._feeds_processed += 1
                
                # Rate limit delay between feeds
                if i < len(sorted_feeds) - 1:
                    is_reddit = 'reddit.com' in feed_url.lower()
                    delay = REDDIT_RATE_LIMIT_DELAY_S if is_reddit else RATE_LIMIT_DELAY_S
                    time.sleep(delay)
                    
            except Exception as e:
                errors.append(f"{feed_url}: {e}")
                if self._logger:
                    self._logger.error("Feed %s failed: %s", feed_url, e)
        
        return WorkerResponse(
            msg_type=MessageType.RSS_RESULT,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=len(errors) < len(feed_urls),
            payload={
                "images": all_images,
                "image_count": len(all_images),
                "feeds_processed": len(sorted_feeds),
                "errors": errors if errors else None,
            },
            processing_time_ms=(time.time() - start) * 1000,
        )
    
    def _fetch_feed(self, feed_url: str, max_images: int) -> List[Dict]:
        """Fetch and parse a single feed, returning image metadata."""
        if not FEEDPARSER_AVAILABLE:
            raise RuntimeError("feedparser is required for RSSWorker")
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests is required for RSSWorker")
        
        images: List[Dict] = []
        is_reddit = 'reddit.com' in feed_url.lower()
        
        # Check if we should skip Reddit fetches to preserve quota for widgets
        if is_reddit:
            try:
                from core.reddit_rate_limiter import RedditRateLimiter, RateLimitPriority
                if RedditRateLimiter.should_skip_for_quota(priority=RateLimitPriority.NORMAL):
                    if self._logger:
                        self._logger.info("[RATE_LIMIT] Skipping RSS worker Reddit fetch to preserve quota for widgets")
                    return []
            except ImportError:
                pass
        
        # Fetch feed
        try:
            if is_reddit and '.json' in feed_url:
                images = self._parse_reddit_json(feed_url, max_images)
            else:
                images = self._parse_rss_feed(feed_url, max_images)
        except Exception as e:
            if self._logger:
                self._logger.error("Parse failed for %s: %s", feed_url, e)
            raise
        
        return images
    
    def _parse_rss_feed(self, feed_url: str, max_images: int) -> List[Dict]:
        """Parse a standard RSS/Atom feed."""
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and feed.bozo_exception:
            if self._logger:
                self._logger.warning("Feed parse warning: %s", feed.bozo_exception)
        
        images: List[Dict] = []
        priority = self._get_source_priority(feed_url)
        
        for entry in feed.entries[:max_images * 2]:  # Fetch extra in case some fail
            if len(images) >= max_images:
                break
            
            # Try to find image URL
            image_url = self._extract_image_url(entry)
            if not image_url:
                continue
            
            # Generate metadata
            title = getattr(entry, 'title', 'Untitled')
            source_id = hashlib.md5(image_url.encode()).hexdigest()[:12]
            
            # Download if cache directory set
            local_path = None
            if self._cache_dir:
                local_path = self._download_image(image_url, source_id)
                if not local_path:
                    continue  # Skip if download failed
            
            images.append({
                "source_type": "RSS",
                "source_id": source_id,
                "url": image_url,
                "local_path": str(local_path) if local_path else None,
                "title": title,
                "priority": priority,
                "timestamp": time.time(),
            })
            
            self._images_downloaded += 1
        
        return images
    
    def _parse_reddit_json(self, feed_url: str, max_images: int) -> List[Dict]:
        """Parse Reddit JSON feed."""
        headers = {
            'User-Agent': 'SRPSS/2.0 (Windows; Screensaver)',
        }
        
        response = requests.get(
            feed_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        
        data = response.json()
        images: List[Dict] = []
        priority = self._get_source_priority(feed_url)
        
        posts = data.get('data', {}).get('children', [])
        
        for post in posts[:max_images * 2]:
            if len(images) >= max_images:
                break
            
            post_data = post.get('data', {})
            
            # Skip non-image posts
            if post_data.get('is_self', True):
                continue
            
            # Get image URL
            image_url = post_data.get('url', '')
            
            # Check for valid image extension
            if not self._is_image_url(image_url):
                # Try preview images
                preview = post_data.get('preview', {})
                preview_images = preview.get('images', [])
                if preview_images:
                    image_url = preview_images[0].get('source', {}).get('url', '')
                    # Decode HTML entities
                    image_url = image_url.replace('&amp;', '&')
            
            if not self._is_image_url(image_url):
                continue
            
            title = post_data.get('title', 'Untitled')
            source_id = post_data.get('id', hashlib.md5(image_url.encode()).hexdigest()[:12])
            
            # Download if cache directory set
            local_path = None
            if self._cache_dir:
                local_path = self._download_image(image_url, source_id)
                if not local_path:
                    continue
            
            images.append({
                "source_type": "RSS",
                "source_id": source_id,
                "url": image_url,
                "local_path": str(local_path) if local_path else None,
                "title": title,
                "priority": priority,
                "timestamp": time.time(),
                "subreddit": post_data.get('subreddit', ''),
            })
            
            self._images_downloaded += 1
        
        return images
    
    def _extract_image_url(self, entry) -> Optional[str]:
        """Extract image URL from a feed entry."""
        # Check enclosures
        if hasattr(entry, 'enclosures'):
            for enc in entry.enclosures:
                url = enc.get('url', '')
                if self._is_image_url(url):
                    return url
        
        # Check media content
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                url = media.get('url', '')
                if self._is_image_url(url):
                    return url
        
        # Check media thumbnail
        if hasattr(entry, 'media_thumbnail'):
            for thumb in entry.media_thumbnail:
                url = thumb.get('url', '')
                if self._is_image_url(url):
                    return url
        
        # Check link
        link = getattr(entry, 'link', '')
        if self._is_image_url(link):
            return link
        
        return None
    
    def _is_image_url(self, url: str) -> bool:
        """Check if URL points to an image."""
        if not url:
            return False
        
        parsed = urlparse(url.lower())
        path = parsed.path
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
        return any(path.endswith(ext) for ext in image_extensions)
    
    def _download_image(self, url: str, source_id: str) -> Optional[Path]:
        """Download an image to cache directory."""
        if not self._cache_dir:
            return None
        
        try:
            # Determine extension
            parsed = urlparse(url)
            ext = Path(parsed.path).suffix.lower() or '.jpg'
            
            cache_path = self._cache_dir / f"{source_id}{ext}"
            
            # Skip if already cached
            if cache_path.exists():
                return cache_path
            
            # Download
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT_S,
                headers={'User-Agent': 'SRPSS/2.0'},
            )
            response.raise_for_status()
            
            # Validate size
            if len(response.content) < MIN_IMAGE_SIZE_BYTES:
                return None
            
            # Save to cache
            cache_path.write_bytes(response.content)
            
            # Also save to permanent directory if configured
            if self._save_dir:
                save_path = self._save_dir / f"{source_id}{ext}"
                if not save_path.exists():
                    save_path.write_bytes(response.content)
            
            return cache_path
            
        except Exception as e:
            if self._logger:
                self._logger.debug("Download failed for %s: %s", url, e)
            return None
    
    def _get_source_priority(self, url: str) -> int:
        """Get priority for a feed URL based on domain."""
        url_lower = url.lower()
        for domain, priority in SOURCE_PRIORITY.items():
            if domain in url_lower:
                return priority
        return 50
    
    def _handle_config(self, msg: WorkerMessage) -> WorkerResponse:
        """Handle configuration update."""
        cache_dir = msg.payload.get("cache_dir")
        save_dir = msg.payload.get("save_dir")
        
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        if save_dir:
            self._save_dir = Path(save_dir)
            self._save_dir.mkdir(parents=True, exist_ok=True)
        
        return WorkerResponse(
            msg_type=MessageType.CONFIG_UPDATE,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
        )
    
    def _cleanup(self) -> None:
        """Log final statistics."""
        if self._logger:
            self._logger.info(
                "RSS stats: %d feeds, %d images downloaded",
                self._feeds_processed,
                self._images_downloaded,
            )


def rss_worker_main(request_queue: Queue, response_queue: Queue) -> None:
    """Entry point for RSS worker process."""
    import sys
    import traceback
    
    sys.stderr.write("=== RSS Worker: Process started ===\n")
    sys.stderr.flush()
    
    try:
        if not FEEDPARSER_AVAILABLE:
            sys.stderr.write("RSS Worker FATAL: feedparser not available\n")
            sys.stderr.flush()
            raise RuntimeError("feedparser is required for RSSWorker")
        
        sys.stderr.write("RSS Worker: Creating worker instance...\n")
        sys.stderr.flush()
        worker = RSSWorker(request_queue, response_queue)
        
        sys.stderr.write("RSS Worker: Starting main loop...\n")
        sys.stderr.flush()
        worker.run()
        
        sys.stderr.write("RSS Worker: Exiting normally\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"RSS Worker CRASHED: {e}\n")
        sys.stderr.write(f"RSS Worker crash traceback:\n{''.join(traceback.format_exc())}\n")
        sys.stderr.flush()
        raise
    
    if not REQUESTS_AVAILABLE:
        sys.stderr.write("RSS Worker FATAL: requests not available\n")
        sys.stderr.flush()
        raise RuntimeError("requests is required for RSSWorker")
