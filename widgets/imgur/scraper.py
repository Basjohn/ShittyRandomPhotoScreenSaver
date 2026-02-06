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


def _slugify_title(title: str) -> str:
    """Convert a title to a URL-safe slug matching Imgur's format.
    
    Examples:
        "Watching" -> "watching"
        "Photo of dog Panko every day" -> "photo-of-dog-panko-every-day"
    """
    if not title:
        return ""
    # Convert to lowercase
    slug = title.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    # Limit length (Imgur seems to truncate long titles)
    if len(slug) > 50:
        slug = slug[:50].rsplit('-', 1)[0]  # Cut at last word boundary
    return slug

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
# Match full gallery path including title slug: /gallery/title-slug-id or /gallery/id
GALLERY_LINK_PATTERN = re.compile(r'/gallery/([a-zA-Z0-9_-]+)')
# Match gallery/album with full path including title
GALLERY_PATH_PATTERN = re.compile(r'/(gallery|a)/([a-zA-Z0-9_-]+)')
POST_ID_PATTERN = re.compile(r'/(gallery|a)/([a-zA-Z0-9]+)')

# Regex for gallery page parsing (full-size image extraction)
OG_IMAGE_PATTERN = re.compile(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\'>]+)["\']', re.IGNORECASE)
OG_IMAGE_ALT_PATTERN = re.compile(r'<meta[^>]*content=["\']([^"\'>]+)["\'][^>]*property=["\']og:image["\']', re.IGNORECASE)


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
    
    # Full-size URL from gallery page parsing (if available)
    full_size_url: str = ""
    
    def get_large_url(self) -> str:
        """Get the large version URL (prefers full-size from gallery parsing)."""
        if self.full_size_url:
            return self.full_size_url
        return f"https://i.imgur.com/{self.id}.{self.extension}"
    
    def get_original_url(self) -> str:
        """Get the original size URL (prefers full-size from gallery parsing)."""
        if self.full_size_url:
            return self.full_size_url
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
    
    def __init__(self, thread_manager=None) -> None:
        """Initialize the scraper with rate limiting state.
        
        Conservative rate limiting to prevent hitting Imgur's limits:
        - Max 24 requests per 10 minutes (2.4 req/min)
        - Track request count and enforce cooldown before limit
        - Rely on cache to minimize requests
        
        Uses simple lock for data protection (per policy allows locks for simple data).
        """
        self._thread_manager = thread_manager
        self._rate_lock = threading.Lock()  # Simple data protection (per policy)
        self._shutdown_event = threading.Event()
        self._last_request_time: float = 0.0
        self._backoff_ms: int = MIN_REQUEST_INTERVAL_MS
        self._consecutive_failures: int = 0
        # Request tracking for conservative rate limiting
        self._request_timestamps: list = []  # Track last N request times
        self._max_requests_per_window: int = 24  # Conservative: 24 per 10min (2.4 req/min)
        self._window_seconds: int = 600  # 10 minutes
        
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
    
    def _is_approaching_rate_limit(self) -> bool:
        """Check if we're approaching rate limit (should use cache instead).
        
        Returns True if we've made too many requests in the time window.
        """
        with self._rate_lock:
            now = time.time()
            # Remove timestamps outside the window
            cutoff = now - self._window_seconds
            self._request_timestamps = [ts for ts in self._request_timestamps if ts > cutoff]
            
            # Check if we're at 90% of limit (conservative)
            return len(self._request_timestamps) >= int(self._max_requests_per_window * 0.9)
    
    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits."""
        with self._rate_lock:
            now = time.time() * 1000  # Convert to ms
            elapsed = now - (self._last_request_time * 1000) if self._last_request_time > 0 else float('inf')
            wait_time = self._backoff_ms - elapsed
            
            if wait_time > 0:
                if self._shutdown_event.wait(wait_time / 1000.0):
                    return  # Shutdown requested
            
            self._last_request_time = time.time()
            # Track this request
            self._request_timestamps.append(time.time())
    
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
            # Try to find gallery/post path and image ID separately
            gallery_path = None  # Full path including title slug (e.g., "watching-8ayb0WE")
            img_id = None        # For the actual image file (just the ID part)
            
            # PRIORITY 1: Check href for gallery/album link (this is what we want to open)
            href = element.get("href", "")
            if href:
                # Try to capture full path with title slug: /gallery/title-slug-id
                match = GALLERY_PATH_PATTERN.search(href)
                if match:
                    gallery_path = match.group(2)  # Full path including title slug
                    # Extract just the ID from the end (after last hyphen if present)
                    # Format is usually "title-slug-ID" where ID is 7-8 chars
                    parts = gallery_path.split('-')
                    if len(parts) > 1 and len(parts[-1]) >= 5:
                        img_id = parts[-1]  # Last part is usually the ID
                    else:
                        img_id = gallery_path  # No title slug, just ID
            
            # PRIORITY 2: Check data-id attribute (fallback for image ID)
            if not img_id and element.get("data-id"):
                img_id = element.get("data-id")
                if not gallery_path:
                    gallery_path = img_id  # Use as gallery path if we don't have one
            
            # PRIORITY 3: Check for img src (last resort)
            if not img_id:
                img = element.find("img")
                if img:
                    src = img.get("src", "") or img.get("data-src", "")
                    # Extract ID from URL like //i.imgur.com/abc123l.jpg
                    match = re.search(r'i\.imgur\.com/([a-zA-Z0-9]+)\.', src)
                    if match:
                        img_id = match.group(1)
                        # Remove size suffix if present (t,m,s,l,h)
                        if img_id and len(img_id) > 5 and img_id[-1] in "tmslh":
                            img_id = img_id[:-1]
                        if not gallery_path:
                            gallery_path = img_id
            
            if not img_id or len(img_id) < 5:
                return None
            if not gallery_path:
                gallery_path = img_id
            
            # Determine if animated (GIF/MP4)
            is_animated = False
            extension = "jpg"
            
            # Check for video or gif indicators
            if element.find("video") or "gif" in str(element).lower():
                is_animated = True
                extension = "gif"
            
            # Build URLs - modern Imgur no longer supports size suffixes
            # The old suffix system (t,m,s,l,h) is deprecated
            # Scraping now only provides 160x160 thumbnails via i.imgur.com
            direct_url = f"https://i.imgur.com/{img_id}.{extension}"
            
            # Extract title if available
            title = ""
            title_elem = element.find(class_="post-title") or element.find("h2")
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Build gallery URL with title slug if we have a title
            # Format: https://imgur.com/gallery/title-slug-ID
            if title and gallery_path == img_id:
                # We only have an ID, not a full path, so construct it from title
                title_slug = _slugify_title(title)
                if title_slug:
                    gallery_path = f"{title_slug}-{img_id}"
            
            gallery_url = f"https://imgur.com/gallery/{gallery_path}"
            
            return ImgurImage(
                id=img_id,
                url=direct_url,
                thumbnail_url="",  # No thumbnails needed
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
            
            # Fallback: regex search for gallery paths in entire HTML
            # Note: Modern Imgur HTML doesn't contain title slugs, only IDs
            # We can't construct proper URLs without titles in fallback mode
            if len(images) < 5:
                for match in GALLERY_LINK_PATTERN.finditer(html):
                    gallery_path = match.group(1)  # Usually just an ID
                    # Extract just the ID from the end for deduplication
                    parts = gallery_path.split('-')
                    if len(parts) > 1 and len(parts[-1]) >= 5:
                        img_id = parts[-1]  # Last part is the ID
                    else:
                        img_id = gallery_path  # No title slug, just ID
                    
                    if img_id not in seen_ids and len(img_id) >= 5:
                        seen_ids.add(img_id)
                        # Fallback URLs won't have title slugs since we have no title text
                        images.append(ImgurImage(
                            id=img_id,
                            url=f"https://i.imgur.com/{img_id}.jpg",
                            thumbnail_url="",  # No thumbnails needed
                            gallery_url=f"https://imgur.com/gallery/{gallery_path}",
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
    
    def fetch_full_size_url(self, image: ImgurImage) -> Optional[str]:
        """Fetch full-size image URL from gallery page via og:image meta tag.
        
        This parses the gallery page to extract the og:image URL which
        contains the full-resolution image (typically 1920px or original).
        
        Args:
            image: ImgurImage with gallery_url set
            
        Returns:
            Full-size URL or None if parsing failed
        """
        if not image.gallery_url:
            return None
        
        self._wait_for_rate_limit()
        
        try:
            response = requests.get(
                image.gallery_url,
                headers=self._get_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
            
            if response.status_code == 429:
                self._record_failure(is_rate_limit=True)
                return None
            
            if response.status_code != 200:
                self._record_failure()
                return None
            
            # Parse og:image from HTML (much faster than full BeautifulSoup parse)
            html = response.text
            
            # Try primary pattern
            match = OG_IMAGE_PATTERN.search(html)
            if not match:
                # Try alternate pattern (content before property)
                match = OG_IMAGE_ALT_PATTERN.search(html)
            
            if match:
                url = match.group(1)
                # Validate it's an imgur image URL
                if 'imgur.com' in url and not url.endswith('.gif'):
                    self._record_success()
                    logger.debug("[IMGUR] Parsed full-size URL: %s", url)
                    return url
            
            self._record_failure()
            return None
            
        except Exception as e:
            self._record_failure()
            logger.debug("[IMGUR] Gallery parse failed for %s: %s", image.id, e)
            return None
    
    def enrich_images_with_full_urls(
        self,
        images: List[ImgurImage],
        max_parallel: int = 3,
        timeout_per_image: float = 5.0,
    ) -> List[ImgurImage]:
        """Enrich images with full-size URLs via parallel gallery page parsing.
        
        Fetches gallery pages in parallel to extract og:image URLs.
        Uses ThreadManager IO pool for parallel fetching when available,
        falls back to sequential fetching otherwise.
        
        Args:
            images: List of ImgurImage to enrich
            max_parallel: Maximum concurrent requests (keep low to avoid rate limits)
            timeout_per_image: Timeout per image fetch
            
        Returns:
            List of images (modified in place with full_size_url set where available)
        """
        if not images:
            return images
        
        start_time = time.time()
        enriched_count = 0
        results_lock = threading.Lock()
        remaining = threading.Event()
        pending = [len(images)]
        
        def _enrich_single(img: "ImgurImage") -> None:
            nonlocal enriched_count
            try:
                full_url = self.fetch_full_size_url(img)
                if full_url:
                    img.full_size_url = full_url
                    with results_lock:
                        enriched_count += 1
            except Exception as e:
                logger.debug("[IMGUR] Failed to enrich %s: %s", img.id, e)
            finally:
                with results_lock:
                    pending[0] -= 1
                    if pending[0] <= 0:
                        remaining.set()
        
        if self._thread_manager:
            for img in images:
                self._thread_manager.submit_io_task(
                    _enrich_single, img,
                    task_id=f"imgur_enrich_{img.id}",
                )
            remaining.wait(timeout=timeout_per_image * len(images))
        else:
            # Sequential fallback when no ThreadManager available
            for img in images:
                _enrich_single(img)
        
        elapsed = time.time() - start_time
        logger.info("[IMGUR] Enriched %d/%d images with full-size URLs in %.2fs",
                   enriched_count, len(images), elapsed)
        
        return images
