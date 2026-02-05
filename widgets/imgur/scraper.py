"""Imgur Scraper Module.

Handles web scraping of Imgur tag pages to extract image URLs.
Uses BeautifulSoup for HTML parsing since Imgur API is closed.

Thread Safety:
- All scraping runs via ThreadManager.submit_io_task()
- Rate limiting is thread-safe via atomic state
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import threading

import requests
from bs4 import BeautifulSoup

from core.logging.logger import get_logger
from core.reddit_rate_limiter import get_reddit_user_agent

logger = get_logger(__name__)

# Imgur URL patterns
IMGUR_TAG_URL = "https://imgur.com/t/{tag}"
IMGUR_HOT_URL = "https://imgur.com/hot"
IMGUR_GALLERY_URL = "https://imgur.com/gallery/{id}"
IMGUR_DIRECT_IMAGE_URL = "https://i.imgur.com/{id}{suffix}.{ext}"

# Image suffixes for different sizes
SUFFIX_THUMBNAIL = "t"  # 160x160
SUFFIX_SMALL = "m"      # 320x320
SUFFIX_LARGE = "l"      # 640x640
SUFFIX_HUGE = "h"       # 1024x1024
SUFFIX_ORIGINAL = ""    # Original size

# Rate limiting constants
MIN_REQUEST_INTERVAL_MS = 500  # 500ms between requests
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_MS = 60000  # 60 seconds max backoff
DEFAULT_TIMEOUT = 10  # seconds

# Regex to extract image IDs from Imgur HTML
IMAGE_ID_PATTERN = re.compile(r'data-id=["\']([a-zA-Z0-9]+)["\']')
GALLERY_LINK_PATTERN = re.compile(r'/gallery/([a-zA-Z0-9]+)')
POST_ID_PATTERN = re.compile(r'/(gallery|a)/([a-zA-Z0-9]+)')


@dataclass
class ImgurImage:
    """Represents a single Imgur image."""
    id: str
    url: str
    thumbnail_url: str
    gallery_url: str
    is_animated: bool = False
    extension: str = "jpg"
    title: str = ""
    
    def get_large_url(self) -> str:
        """Get the large (640px) version URL."""
        return f"https://i.imgur.com/{self.id}l.{self.extension}"
    
    def get_original_url(self) -> str:
        """Get the original size URL."""
        return f"https://i.imgur.com/{self.id}.{self.extension}"


@dataclass
class ScrapeResult:
    """Result of a scrape operation."""
    images: List[ImgurImage] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None
    rate_limited: bool = False
    retry_after_ms: int = 0


class ImgurScraper:
    """Scrapes Imgur tag pages for image URLs.
    
    Uses BeautifulSoup to parse HTML and extract image IDs.
    Implements exponential backoff for rate limiting.
    
    Thread Safety:
        - _last_request_time protected by _rate_lock
        - _backoff_ms protected by _rate_lock
        - All state mutations use lock
    """
    
    # Popular tags for dropdown
    POPULAR_TAGS = [
        ("most_viral", "Most Viral"),
        ("memes", "Memes"),
        ("aww", "Aww (Cute Animals)"),
        ("dog", "Dogs"),
        ("cats", "Cats"),
        ("funny", "Funny"),
        ("earthporn", "Earth Porn (Landscapes)"),
        ("architecture", "Architecture"),
        ("wallpapers", "Wallpapers"),
        ("gifs", "GIFs"),
        ("pics", "Pics"),
    ]
    
    def __init__(self) -> None:
        """Initialize the scraper with rate limiting state."""
        self._rate_lock = threading.Lock()
        self._last_request_time: float = 0.0
        self._backoff_ms: int = MIN_REQUEST_INTERVAL_MS
        self._consecutive_failures: int = 0
        
    def _get_headers(self) -> dict:
        """Get request headers with rotated User-Agent."""
        return {
            "User-Agent": get_reddit_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    
    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits."""
        with self._rate_lock:
            now = time.time() * 1000  # Convert to ms
            elapsed = now - (self._last_request_time * 1000) if self._last_request_time > 0 else float('inf')
            wait_time = self._backoff_ms - elapsed
            
            if wait_time > 0:
                time.sleep(wait_time / 1000.0)
            
            self._last_request_time = time.time()
    
    def _record_success(self) -> None:
        """Record a successful request, reset backoff."""
        with self._rate_lock:
            self._consecutive_failures = 0
            self._backoff_ms = MIN_REQUEST_INTERVAL_MS
    
    def _record_failure(self, is_rate_limit: bool = False) -> None:
        """Record a failed request, increase backoff."""
        with self._rate_lock:
            self._consecutive_failures += 1
            if is_rate_limit:
                self._backoff_ms = min(
                    int(self._backoff_ms * BACKOFF_MULTIPLIER),
                    MAX_BACKOFF_MS
                )
                logger.warning(
                    "[IMGUR] Rate limited, backoff increased to %dms",
                    self._backoff_ms
                )
    
    def _build_tag_url(self, tag: str) -> str:
        """Build the URL for a tag page."""
        if tag == "most_viral" or tag == "hot":
            return IMGUR_HOT_URL
        # Sanitize tag - only alphanumeric and hyphens
        safe_tag = re.sub(r'[^a-zA-Z0-9_-]', '', tag)
        return IMGUR_TAG_URL.format(tag=safe_tag)
    
    def _parse_image_from_element(self, element, soup: BeautifulSoup) -> Optional[ImgurImage]:
        """Parse an image from an HTML element."""
        try:
            # Try to find image ID from various attributes
            img_id = None
            
            # Check data-id attribute
            if element.get("data-id"):
                img_id = element.get("data-id")
            
            # Check href for gallery link
            if not img_id:
                href = element.get("href", "")
                match = GALLERY_LINK_PATTERN.search(href)
                if match:
                    img_id = match.group(1)
            
            # Check for img src
            if not img_id:
                img = element.find("img")
                if img:
                    src = img.get("src", "") or img.get("data-src", "")
                    # Extract ID from URL like //i.imgur.com/abc123l.jpg
                    match = re.search(r'i\.imgur\.com/([a-zA-Z0-9]+)', src)
                    if match:
                        img_id = match.group(1)
                        # Remove size suffix if present
                        if img_id and img_id[-1] in "tmslh":
                            img_id = img_id[:-1]
            
            if not img_id or len(img_id) < 5:
                return None
            
            # Determine if animated (GIF/MP4)
            is_animated = False
            extension = "jpg"
            
            # Check for video or gif indicators
            if element.find("video") or "gif" in str(element).lower():
                is_animated = True
                extension = "gif"
            
            # Build URLs
            thumbnail_url = f"https://i.imgur.com/{img_id}t.jpg"
            direct_url = f"https://i.imgur.com/{img_id}l.{extension}"
            gallery_url = f"https://imgur.com/gallery/{img_id}"
            
            # Extract title if available
            title = ""
            title_elem = element.find(class_="post-title") or element.find("h2")
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            return ImgurImage(
                id=img_id,
                url=direct_url,
                thumbnail_url=thumbnail_url,
                gallery_url=gallery_url,
                is_animated=is_animated,
                extension=extension,
                title=title,
            )
        except Exception as e:
            logger.debug("[IMGUR] Failed to parse image element: %s", e)
            return None
    
    def _parse_html(self, html: str) -> List[ImgurImage]:
        """Parse HTML to extract image data."""
        images: List[ImgurImage] = []
        seen_ids: set = set()
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Try multiple selectors for different Imgur layouts
            selectors = [
                ".post",
                ".Post",
                "[data-id]",
                ".gallery-image",
                ".image-list-link",
                "a[href*='/gallery/']",
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                for elem in elements:
                    img = self._parse_image_from_element(elem, soup)
                    if img and img.id not in seen_ids:
                        seen_ids.add(img.id)
                        images.append(img)
            
            # Fallback: regex search for image IDs in entire HTML
            if len(images) < 5:
                for match in GALLERY_LINK_PATTERN.finditer(html):
                    img_id = match.group(1)
                    if img_id not in seen_ids and len(img_id) >= 5:
                        seen_ids.add(img_id)
                        images.append(ImgurImage(
                            id=img_id,
                            url=f"https://i.imgur.com/{img_id}l.jpg",
                            thumbnail_url=f"https://i.imgur.com/{img_id}t.jpg",
                            gallery_url=f"https://imgur.com/gallery/{img_id}",
                        ))
            
            logger.debug("[IMGUR] Parsed %d images from HTML", len(images))
            
        except Exception as e:
            logger.error("[IMGUR] HTML parsing failed: %s", e)
        
        return images
    
    def scrape_tag(self, tag: str, max_images: int = 50) -> ScrapeResult:
        """Scrape images from an Imgur tag page.
        
        Args:
            tag: Tag name or "most_viral" for hot page
            max_images: Maximum number of images to return
            
        Returns:
            ScrapeResult with images or error information
        """
        self._wait_for_rate_limit()
        
        url = self._build_tag_url(tag)
        logger.info("[IMGUR] Scraping tag '%s' from %s", tag, url)
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
            )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                self._record_failure(is_rate_limit=True)
                return ScrapeResult(
                    success=False,
                    error="Rate limited by Imgur",
                    rate_limited=True,
                    retry_after_ms=retry_after * 1000,
                )
            
            if response.status_code != 200:
                self._record_failure()
                return ScrapeResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                )
            
            # Parse HTML
            images = self._parse_html(response.text)
            
            if not images:
                self._record_failure()
                return ScrapeResult(
                    success=False,
                    error="No images found in response",
                )
            
            self._record_success()
            
            # Limit results
            images = images[:max_images]
            
            logger.info("[IMGUR] Successfully scraped %d images from '%s'", len(images), tag)
            
            return ScrapeResult(
                images=images,
                success=True,
            )
            
        except requests.Timeout:
            self._record_failure()
            return ScrapeResult(
                success=False,
                error="Request timed out",
            )
        except requests.RequestException as e:
            self._record_failure()
            return ScrapeResult(
                success=False,
                error=f"Request failed: {e}",
            )
        except Exception as e:
            self._record_failure()
            logger.exception("[IMGUR] Unexpected error during scrape")
            return ScrapeResult(
                success=False,
                error=f"Unexpected error: {e}",
            )
    
    def download_image(
        self,
        image: ImgurImage,
        target_path: Path,
        size: str = "large",
    ) -> bool:
        """Download an image to the specified path.
        
        Args:
            image: ImgurImage to download
            target_path: Path to save the image
            size: Size variant - "large", "original", "thumbnail"
            
        Returns:
            True if download succeeded
        """
        self._wait_for_rate_limit()
        
        # Select URL based on size
        if size == "original":
            url = image.get_original_url()
        elif size == "thumbnail":
            url = image.thumbnail_url
        else:
            url = image.get_large_url()
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=DEFAULT_TIMEOUT,
                stream=True,
            )
            
            if response.status_code == 429:
                self._record_failure(is_rate_limit=True)
                return False
            
            if response.status_code != 200:
                self._record_failure()
                logger.warning("[IMGUR] Download failed for %s: HTTP %d", image.id, response.status_code)
                return False
            
            # Ensure parent directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self._record_success()
            logger.debug("[IMGUR] Downloaded %s to %s", image.id, target_path)
            return True
            
        except Exception as e:
            self._record_failure()
            logger.error("[IMGUR] Download failed for %s: %s", image.id, e)
            return False
    
    def get_current_backoff_ms(self) -> int:
        """Get current backoff time in milliseconds."""
        with self._rate_lock:
            return self._backoff_ms
