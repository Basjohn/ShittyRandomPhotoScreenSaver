"""Imgur Widget - Main Widget Implementation.

Displays a grid of images from Imgur tags with configurable layout.
Follows all project policies for threading, painting, and lifecycle.

Thread Safety:
- All image fetching via ThreadManager.submit_io_task()
- UI updates via ThreadManager.run_on_ui_thread()
- State protected by threading.Lock()
"""
from __future__ import annotations

import threading
import time
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics,
    QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.performance import widget_paint_sample
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from widgets.shadow_utils import draw_text_with_shadow, draw_rounded_rect_with_shadow
from widgets.imgur.scraper import ImgurScraper, ImgurImage
from widgets.imgur.image_cache import ImgurImageCache

logger = get_logger(__name__)

# Widget constants
DEFAULT_GRID_ROWS = 2
DEFAULT_GRID_COLS = 4
DEFAULT_IMAGE_SPACING = 4
DEFAULT_UPDATE_INTERVAL_SEC = 600  # 10 minutes
MIN_CELL_SIZE = 80
HEADER_HEIGHT = 36
HEADER_PADDING = 8

# Logo path
IMGUR_LOGO_PATH = Path(__file__).resolve().parents[2] / "images" / "Imgur_Icon_2018.png"


class LayoutMode(Enum):
    """Grid layout modes for image display."""
    VERTICAL = "vertical"    # 9:16 aspect ratio cells
    SQUARE = "square"        # 1:1 aspect ratio cells
    HYBRID = "hybrid"        # Auto-detect per image


class ImgurPosition(Enum):
    """Imgur widget position on screen."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class GridCell:
    """Represents a single cell in the image grid."""
    rect: QRect
    image_id: Optional[str] = None
    pixmap: Optional[QPixmap] = None
    gallery_url: str = ""
    aspect_ratio: float = 1.0


class ImgurWidget(BaseOverlayWidget):
    """Imgur widget displaying a grid of images from Imgur tags.
    
    Features:
    - Configurable grid dimensions (rows × columns)
    - Multiple layout modes (vertical, square, hybrid)
    - Paint caching for performance
    - Background image fetching via ThreadManager
    - Click to open in browser
    - LRU disk cache for images
    
    Lifecycle:
    - CREATED → INITIALIZED → ACTIVE ⇄ HIDDEN → DESTROYED
    - Uses BaseOverlayWidget lifecycle management
    """
    
    DEFAULT_FONT_SIZE = 11
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        tag: str = "most_viral",
        position: ImgurPosition = ImgurPosition.TOP_RIGHT,
    ) -> None:
        """Initialize the Imgur widget.
        
        Args:
            parent: Parent widget
            tag: Imgur tag to display
            position: Screen position
        """
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="imgur")
        
        # Defer visibility until fade sync
        self._defer_visibility_for_fade_sync = True
        
        # Configuration
        self._imgur_position = position
        self._tag = tag
        self._custom_tag = ""
        self._grid_rows = DEFAULT_GRID_ROWS
        self._grid_cols = DEFAULT_GRID_COLS
        self._layout_mode = LayoutMode.HYBRID
        self._image_spacing = DEFAULT_IMAGE_SPACING
        self._update_interval_sec = DEFAULT_UPDATE_INTERVAL_SEC
        
        # Image styling
        self._image_border_enabled = True
        self._image_border_width = 2
        self._image_border_color = QColor(255, 255, 255, 255)
        self._image_border_radius = 4
        
        # Header
        self._show_header = True
        self._header_font_size = 14
        self._header_logo: Optional[QPixmap] = None
        
        # Interaction
        self._click_opens_browser = True
        
        # Ensure base styling attributes are initialized (from BaseOverlayWidget)
        # These are set in BaseOverlayWidget.__init__ but we need to ensure they exist
        if not hasattr(self, '_border_color'):
            self._border_color = QColor(255, 255, 255, 80)
        
        # State (protected by simple lock for data protection - per policy allows locks for simple data)
        self._state_lock = threading.Lock()  # Simple data protection (per policy)
        self._images: List[ImgurImage] = []  # Current display window
        self._image_buffer: List[ImgurImage] = []  # Circular buffer of all fetched images
        self._buffer_max_size: int = 100  # Max images in buffer
        self._display_offset: int = 0  # Current position in buffer for display window
        self._grid_cells: List[GridCell] = []
        self._fetching = False
        self._last_fetch_time: float = 0.0
        self._fade_registered = False  # Track if fade sync has been requested
        
        # Paint caching
        self._cached_pixmap: Optional[QPixmap] = None
        self._cache_invalidated = True
        
        # Cell pixmap cache (avoid re-scaling on every paint)
        self._cell_pixmap_cache: Dict[str, QPixmap] = {}  # image_id -> scaled pixmap
        self._cell_cache_size: Tuple[int, int] = (0, 0)  # Cached cell dimensions
        
        # Components
        self._scraper: Optional[ImgurScraper] = None
        self._image_cache: Optional[ImgurImageCache] = None
        
        # Timers
        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        
        # Click tracking
        self._cell_hit_rects: List[Tuple[QRect, str]] = []  # (rect, gallery_url)
        self._header_hit_rect: Optional[QRect] = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug("[IMGUR] Widget created (tag=%s, position=%s)", tag, position.value)
    
    def _setup_ui(self) -> None:
        """Initialize widget appearance."""
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # Non-interactive at widget level
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[IMGUR] Exception suppressed: %s", e)
        
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(False)
        
        # Default size
        self._calculate_size()
        
        # Load header logo
        self._load_header_logo()
        
        # Move offscreen initially
        try:
            self.move(10000, 10000)
        except Exception as e:
            logger.debug("[IMGUR] Exception suppressed: %s", e)
    
    def _load_header_logo(self) -> None:
        """Load the Imgur logo for header."""
        try:
            if IMGUR_LOGO_PATH.exists():
                self._header_logo = QPixmap(str(IMGUR_LOGO_PATH))
                if self._header_logo.isNull():
                    self._header_logo = None
            else:
                logger.debug("[IMGUR] Logo not found at %s", IMGUR_LOGO_PATH)
        except Exception as e:
            logger.debug("[IMGUR] Failed to load logo: %s", e)
            self._header_logo = None
    
    def _calculate_size(self) -> None:
        """Calculate widget size based on grid configuration."""
        cell_width = 120  # Base cell width
        cell_height = self._get_cell_height(cell_width)
        
        width = (cell_width * self._grid_cols) + (self._image_spacing * (self._grid_cols - 1)) + 20
        height = (cell_height * self._grid_rows) + (self._image_spacing * (self._grid_rows - 1))
        
        if self._show_header:
            height += HEADER_HEIGHT + HEADER_PADDING
        
        height += 20  # Padding
        
        self.setMinimumSize(width, height)
        self.setFixedSize(width, height)
    
    def _get_cell_height(self, cell_width: int, image_id: Optional[str] = None) -> int:
        """Get cell height based on layout mode.
        
        For hybrid mode, uses actual image aspect ratio from cache if available.
        """
        if self._layout_mode == LayoutMode.VERTICAL:
            return int(cell_width * 16 / 9)  # 9:16 aspect
        elif self._layout_mode == LayoutMode.SQUARE:
            return cell_width  # 1:1 aspect
        else:  # HYBRID - dynamic based on image
            if image_id and self._image_cache:
                result = self._image_cache.get(image_id)
                if result:
                    _, cached = result
                    if cached.width > 0 and cached.height > 0:
                        aspect = cached.height / cached.width
                        # Clamp aspect ratio to reasonable bounds
                        if aspect > 1.5:  # Portrait
                            return int(cell_width * 1.5)
                        elif aspect < 0.7:  # Landscape
                            return int(cell_width * 0.8)
                        else:  # Near square
                            return int(cell_width * aspect)
            # Default for hybrid when no image info
            return int(cell_width * 1.2)
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh display."""
        self._fetch_images()
    
    def _initialize_impl(self) -> None:
        """Initialize resources (lifecycle hook)."""
        # Create scraper and cache
        self._scraper = ImgurScraper(thread_manager=self._thread_manager)
        self._image_cache = ImgurImageCache()
        logger.debug("[LIFECYCLE] ImgurWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate widget - start fetching (lifecycle hook).
        
        Matches Reddit widget pattern: loads cache SYNCHRONOUSLY before fade
        so widget has content when it appears. This eliminates the perceived
        delay where widget fades in empty then images appear later.
        """
        start_time = time.time()
        logger.info("[IMGUR] === ACTIVATION START ===")
        
        if not self._ensure_thread_manager("ImgurWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
        # SYNC: Load cached images BEFORE building grid (like Reddit does)
        # This ensures widget has content when fade starts
        cache_start = time.time()
        cached_images = self._load_cached_images_sync()
        if cached_images:
            logger.info("[IMGUR] Loaded %d cached images in %.3fs",
                       len(cached_images), time.time() - cache_start)
            with self._state_lock:
                self._images = cached_images
        else:
            logger.info("[IMGUR] No cached images found (%.3fs)", time.time() - cache_start)
        
        # Build grid structure with loaded images
        logger.info("[IMGUR] Building grid structure...")
        self._rebuild_grid_structure()
        self._invalidate_cache()
        logger.info("[IMGUR] Grid structure built in %.3fs", time.time() - start_time)
        
        # Load pixmaps for grid cells SYNCHRONOUSLY (fast - just QPixmap loads)
        # This ensures images are visible when widget fades in
        if cached_images:
            pixmap_start = time.time()
            self._load_pixmaps_sync()
            logger.info("[IMGUR] Pixmaps loaded in %.3fs", time.time() - pixmap_start)
        
        # Request fade sync - widget will be shown by fade coordinator's _starter callback
        # DO NOT call self.show() here - that causes widget to appear before fade starts
        # and puts it behind the compositor. The _starter callback in _request_fade_sync_if_needed
        # calls _start_widget_fade_in which handles showing the widget at the right time.
        fade_start = time.time()
        logger.info("[IMGUR] Requesting fade sync (content ready, will show via fade)...")
        self._request_fade_sync_if_needed()
        logger.info("[IMGUR] Fade sync requested in %.3fs", time.time() - fade_start)
        
        # Schedule periodic updates with jitter
        self._schedule_timer()
        
        # Fetch fresh images in background (with gallery parsing for full-size URLs)
        logger.info("[IMGUR] Submitting background fetch...")
        self._fetch_images()
        
        logger.info("[IMGUR] === ACTIVATION COMPLETE in %.3fs ===", time.time() - start_time)
    
    def _deactivate_impl(self) -> None:
        """Deactivate widget - stop fetching (lifecycle hook)."""
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[IMGUR] Exception suppressed: %s", e)
            self._update_timer_handle = None
        
        with self._state_lock:
            self._images.clear()
            self._grid_cells.clear()
        
        logger.debug("[LIFECYCLE] ImgurWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up resources (lifecycle hook)."""
        self._deactivate_impl()
        
        # Save cache
        if self._image_cache:
            self._image_cache.cleanup()
        
        self._cached_pixmap = None
        logger.debug("[LIFECYCLE] ImgurWidget cleaned up")
    
    def _schedule_timer(self) -> None:
        """Schedule the update timer with jitter."""
        # Add ±60s jitter to desync from other widgets
        jitter_ms = random.randint(-60 * 1000, 60 * 1000)
        interval_ms = (self._update_interval_sec * 1000) + jitter_ms
        
        self._update_timer_handle = create_overlay_timer(
            self, interval_ms, self._fetch_images,
            description="ImgurWidget refresh"
        )
        
        if is_perf_metrics_enabled():
            logger.debug("[PERF] ImgurWidget: refresh interval %.1f min (jitter: %+.1f s)",
                        interval_ms / 60000, jitter_ms / 1000)
    
    def _load_cached_images_sync(self) -> List[ImgurImage]:
        """Load cached images SYNCHRONOUSLY for immediate display.
        
        Called during activation to ensure widget has content before fade.
        This matches Reddit widget's pattern of sync cache loading.
        
        Returns:
            List of ImgurImage from cache (may be empty)
        """
        if not self._image_cache:
            return []
        
        cached = self._image_cache.get_all_cached()
        if not cached:
            return []
        
        # Take up to grid size images
        needed = self._grid_rows * self._grid_cols
        cached = cached[:needed]
        
        # Create image list from cache metadata
        images = [
            ImgurImage(
                id=c.id,
                url=f"https://i.imgur.com/{c.id}.jpg",
                thumbnail_url="",
                gallery_url=c.gallery_url,
                is_animated=c.is_animated,
            )
            for c in cached
        ]
        
        return images
    
    def _load_pixmaps_sync(self) -> None:
        """Load pixmaps for grid cells SYNCHRONOUSLY.
        
        Called during activation after cache load to ensure images
        are ready when widget fades in. Fast operation (just QPixmap loads
        from disk cache, no network).
        """
        if not self._image_cache:
            return
        
        with self._state_lock:
            cells = list(self._grid_cells)
        
        loaded_count = 0
        for cell in cells:
            if cell.image_id and not cell.pixmap:
                pixmap = self._image_cache.get_pixmap(cell.image_id)
                if pixmap and not pixmap.isNull():
                    cell.pixmap = pixmap
                    loaded_count += 1
        
        if loaded_count > 0:
            self._invalidate_cache()
            logger.debug("[IMGUR] Sync-loaded %d pixmaps", loaded_count)
    
    def _load_from_cache_background(self) -> None:
        """Load images from disk cache in background thread.
        
        Updates UI via invoke_in_ui_thread when done.
        """
        start_time = time.time()
        logger.info("[IMGUR] === CACHE LOAD START (background thread) ===")
        
        if not self._image_cache:
            logger.info("[IMGUR] No image cache available")
            return
        
        # No thumbnail generation needed - using full resolution images
        
        cached = self._image_cache.get_all_cached()
        if not cached:
            logger.info("[IMGUR] No cached images found")
            return
        
        # Take up to grid size images
        needed = self._grid_rows * self._grid_cols
        cached = cached[:needed]
        
        # Create image list
        images = [
            ImgurImage(
                id=c.id,
                url=f"https://i.imgur.com/{c.id}.jpg",
                thumbnail_url="",  # No thumbnails
                gallery_url=c.gallery_url,
                is_animated=c.is_animated,
            )
            for c in cached
        ]
        
        logger.info("[IMGUR] Loaded %d cached images in %.3fs, updating UI", len(images), time.time() - start_time)
        
        # Update UI on main thread
        def update_ui():
            ui_start = time.time()
            logger.info("[IMGUR] Updating UI with cached images...")
            with self._state_lock:
                self._images = images
            self._rebuild_grid_structure()
            self._invalidate_cache()
            self.update()
            logger.info("[IMGUR] UI updated in %.3fs", time.time() - ui_start)
            # Load pixmaps in background
            if self._thread_manager:
                logger.info("[IMGUR] Submitting pixmap load to background...")
                self._thread_manager.submit_io_task(self._load_pixmaps_background)
        
        ThreadManager.run_on_ui_thread(update_ui)
    
    
    def _fetch_images(self) -> None:
        """Fetch images from Imgur (called on timer or manually)."""
        with self._state_lock:
            if self._fetching:
                return
            self._fetching = True
        
        if not self._thread_manager:
            with self._state_lock:
                self._fetching = False
            return
        
        # Submit fetch task
        self._thread_manager.submit_io_task(self._fetch_images_worker)
    
    def _fetch_images_worker(self) -> None:
        """Worker function for fetching images (runs in background thread)."""
        try:
            if not self._scraper:
                return
            
            # Check if we're approaching rate limit - use cache instead
            if self._scraper._is_approaching_rate_limit():
                logger.info("[IMGUR] Approaching rate limit, relying on cache instead of scraping")
                # Just refresh from cache
                if self._image_cache:
                    cached = self._image_cache.get_all_cached()
                    if cached:
                        ThreadManager.run_on_ui_thread(lambda: self._load_from_cache())
                return
            
            # Determine tag to use
            tag = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
            
            # Scrape tag page
            needed = self._grid_rows * self._grid_cols
            result = self._scraper.scrape_tag(tag, max_images=needed * 2)
            
            if not result.success:
                logger.warning("[IMGUR] Scrape failed: %s", result.error)
                return
            
            if not result.images:
                logger.warning("[IMGUR] No images returned from scrape")
                return
            
            # Enrich images with full-size URLs via gallery page parsing
            # Uses separate thread pool to avoid deadlocking main ThreadManager
            images_to_display = result.images[:needed]
            logger.info("[IMGUR] Enriching %d images with full-size URLs...", len(images_to_display))
            images_to_display = self._scraper.enrich_images_with_full_urls(
                images_to_display,
                max_parallel=3,  # Keep low to avoid rate limits
                timeout_per_image=5.0,
            )
            
            if images_to_display:
                logger.info("[IMGUR] Updating UI with %d enriched images", len(images_to_display))
                ThreadManager.run_on_ui_thread(
                    lambda: self._on_images_fetched(images_to_display)
                )
                
                # Download images concurrently (4 at a time) using ThreadManager
                logger.debug("[IMGUR] Starting concurrent download of %d images", len(images_to_display))
                self._download_images_concurrent(images_to_display, max_concurrent=4)
            else:
                logger.warning("[IMGUR] No images to display")
            
        except Exception as e:
            logger.error("[IMGUR] Fetch worker failed: %s", e)
        finally:
            with self._state_lock:
                self._fetching = False
                self._last_fetch_time = time.time()
    
    def _download_and_cache(self, image: ImgurImage) -> bool:
        """Download an image and add to cache."""
        if not self._image_cache or not self._scraper:
            logger.debug("[IMGUR] Cannot download - cache or scraper missing")
            return False
        
        # Check if already cached
        if self._image_cache.has(image.id):
            logger.debug("[IMGUR] Image %s already in cache", image.id)
            return True
        
        # Download image
        import requests
        from core.reddit_rate_limiter import get_reddit_user_agent
        
        try:
            # Prefer full_size_url from gallery parsing, fallback to base URL
            url = image.get_large_url()  # Returns full_size_url if available
            logger.debug("[IMGUR] Downloading %s from %s", image.id, url)
            response = requests.get(
                url,
                headers={"User-Agent": get_reddit_user_agent()},
                timeout=10,
            )
            
            # Fallback to base URL if full-size fails
            if response.status_code != 200 and image.full_size_url:
                fallback_url = f"https://i.imgur.com/{image.id}.{image.extension}"
                logger.debug("[IMGUR] Full-size failed, trying base URL fallback: %s", fallback_url)
                response = requests.get(
                    fallback_url,
                    headers={"User-Agent": get_reddit_user_agent()},
                    timeout=10,
                )
                if response.status_code != 200:
                    logger.debug("[IMGUR] Download failed for %s: HTTP %d", image.id, response.status_code)
                    return False
            
            logger.debug("[IMGUR] Downloaded %s (%d bytes), caching...", image.id, len(response.content))
            
            # Cache it
            cached = self._image_cache.put(
                image.id,
                response.content,
                extension=image.extension,
                is_animated=image.is_animated,
                gallery_url=image.gallery_url,
            )
            
            if cached:
                logger.debug("[IMGUR] Cached %s successfully", image.id)
            else:
                logger.debug("[IMGUR] Failed to cache %s", image.id)
            
            return cached is not None
            
        except Exception as e:
            logger.debug("[IMGUR] Download failed for %s: %s", image.id, e)
            return False
    
    def _download_images_concurrent(self, images: List[ImgurImage], max_concurrent: int = 4) -> None:
        """Download images concurrently using ThreadManager.
        
        Args:
            images: List of images to download
            max_concurrent: Maximum concurrent downloads (default 4)
        """
        import threading
        
        if not images:
            return
        
        # Use a semaphore to limit concurrent downloads
        semaphore = threading.Semaphore(max_concurrent)
        download_count = [0]  # Use list for mutable counter in closure
        
        def download_with_semaphore(img: ImgurImage) -> bool:
            with semaphore:
                result = self._download_and_cache(img)
                if result:
                    download_count[0] += 1
                    # Refresh grid on UI thread after each successful download
                    ThreadManager.run_on_ui_thread(self._refresh_grid_from_cache)
                return result
        
        # Submit all downloads to ThreadManager IO pool
        for img in images:
            if self._thread_manager:
                self._thread_manager.submit_io_task(
                    lambda i=img: download_with_semaphore(i),
                    task_id=f"imgur_download_{img.id}",
                )
            else:
                # Fallback to direct download if no ThreadManager
                download_with_semaphore(img)
        
        logger.debug("[IMGUR] Submitted %d downloads (max %d concurrent)", len(images), max_concurrent)
    
    def _request_fade_sync_if_needed(self) -> None:
        """Request fade sync if not already registered (widget appears immediately)."""
        with self._state_lock:
            should_register = not self._fade_registered
        
        if not should_register:
            logger.info("[IMGUR] Fade already registered, skipping")
            return
        
        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            def _starter() -> None:
                logger.info("[IMGUR] === FADE STARTER CALLED ===")
                try:
                    self._start_widget_fade_in(1500)
                    logger.info("[IMGUR] Fade-in animation started")
                except Exception as e:
                    logger.error("[IMGUR] Fade-in failed: %s", e)
            
            try:
                overlay_name = getattr(self, '_overlay_name', 'imgur')
                logger.info("[IMGUR] Calling parent.request_overlay_fade_sync(name=%s)", overlay_name)
                parent.request_overlay_fade_sync(overlay_name, _starter)
                with self._state_lock:
                    self._fade_registered = True
                logger.info("[IMGUR] Fade sync registered with coordinator")
            except Exception as e:
                logger.error("[IMGUR] Fade sync registration failed: %s", e)
                _starter()
        else:
            # No fade coordinator - just fade in directly
            logger.info("[IMGUR] No fade coordinator, starting fade directly")
            try:
                self._start_widget_fade_in(1500)
                with self._state_lock:
                    self._fade_registered = True
                logger.info("[IMGUR] Direct fade-in started")
            except Exception as e:
                logger.error("[IMGUR] Direct fade-in failed: %s", e)
    
    def _on_images_fetched(self, images: List[ImgurImage]) -> None:
        """Handle fetched images (called on UI thread).
        
        Adds new images to circular buffer and updates display window.
        """
        if not Shiboken.isValid(self):
            return
        needed = self._grid_rows * self._grid_cols
        
        with self._state_lock:
            # Add new images to buffer (avoid duplicates)
            existing_ids = {img.id for img in self._image_buffer}
            for img in images:
                if img.id not in existing_ids:
                    self._image_buffer.append(img)
                    existing_ids.add(img.id)
            
            # Enforce buffer max size (LRU - remove oldest)
            while len(self._image_buffer) > self._buffer_max_size:
                self._image_buffer.pop(0)
            
            # Update display window from buffer
            if len(self._image_buffer) >= needed:
                self._images = self._image_buffer[:needed]
            else:
                self._images = list(self._image_buffer)
        
        self._rebuild_grid()
        self._invalidate_cache()
        self.update()
        
        logger.info("[IMGUR] Updated with %d images (buffer: %d)", len(images), len(self._image_buffer))
        
        # Request fade sync if needed (will be no-op if already registered from cache load)
        self._request_fade_sync_if_needed()
    
    def rotate_images(self) -> None:
        """Rotate display window to show next set of images from buffer with smooth fade."""
        needed = self._grid_rows * self._grid_cols
        
        with self._state_lock:
            if len(self._image_buffer) <= needed:
                return  # Not enough images to rotate
            
            # Advance offset
            self._display_offset = (self._display_offset + needed) % len(self._image_buffer)
            
            # Get new display window
            end_idx = self._display_offset + needed
            if end_idx <= len(self._image_buffer):
                self._images = self._image_buffer[self._display_offset:end_idx]
            else:
                # Wrap around
                self._images = (
                    self._image_buffer[self._display_offset:] +
                    self._image_buffer[:end_idx - len(self._image_buffer)]
                )
        
        # Smooth transition: fade out, rebuild, fade in
        self._start_widget_fade_out(300, callback=lambda: self._complete_rotation())
        logger.debug("[IMGUR] Rotating to offset %d with fade", self._display_offset)
    
    def _complete_rotation(self) -> None:
        """Complete rotation after fade-out - rebuild grid and fade in."""
        self._rebuild_grid_structure()
        self._invalidate_cache()
        self.update()
        # Load pixmaps OFF UI thread
        if self._thread_manager:
            self._thread_manager.submit_io_task(self._load_pixmaps_background)
        self._start_widget_fade_in(300)
    
    def _rebuild_grid_structure(self) -> None:
        """Build grid cell layout WITHOUT loading pixmaps (fast, UI thread safe)."""
        with self._state_lock:
            images = list(self._images)
        
        widget_rect = self.rect()
        padding = 10
        
        # Account for header
        y_offset = padding
        if self._show_header:
            y_offset += HEADER_HEIGHT + HEADER_PADDING
        
        available_width = widget_rect.width() - (padding * 2)
        available_height = widget_rect.height() - y_offset - padding
        
        # Calculate cell dimensions
        cell_width = (available_width - (self._image_spacing * (self._grid_cols - 1))) // self._grid_cols
        cell_height = (available_height - (self._image_spacing * (self._grid_rows - 1))) // self._grid_rows
        
        cell_width = max(cell_width, MIN_CELL_SIZE)
        cell_height = max(cell_height, MIN_CELL_SIZE)
        
        # Build cells (no pixmaps - just structure)
        cells: List[GridCell] = []
        self._cell_hit_rects.clear()
        
        for row in range(self._grid_rows):
            for col in range(self._grid_cols):
                idx = row * self._grid_cols + col
                
                x = padding + col * (cell_width + self._image_spacing)
                y = y_offset + row * (cell_height + self._image_spacing)
                
                rect = QRect(x, y, cell_width, cell_height)
                cell = GridCell(rect=rect)
                
                if idx < len(images):
                    img = images[idx]
                    cell.image_id = img.id
                    cell.gallery_url = img.gallery_url
                    self._cell_hit_rects.append((rect, img.gallery_url))
                
                cells.append(cell)
        
        with self._state_lock:
            self._grid_cells = cells
    
    def _rebuild_grid(self) -> None:
        """Rebuild grid structure and trigger async pixmap loading."""
        self._rebuild_grid_structure()
        # Load pixmaps OFF UI thread
        if self._thread_manager:
            self._thread_manager.submit_io_task(self._load_pixmaps_background)
    
    def _load_pixmaps_background(self) -> None:
        """Load pixmaps for grid cells in background thread.
        
        Updates UI via invoke_in_ui_thread.
        """
        start_time = time.time()
        logger.info("[IMGUR] === PIXMAP LOAD START (background thread) ===")
        
        if not self._image_cache:
            return
        
        # No thumbnail generation needed - using full resolution images
        
        with self._state_lock:
            cells = list(self._grid_cells)
        
        # Load pixmaps for each cell (use thumbnails for speed - they're 600px, good quality)
        loaded_count = 0
        for cell in cells:
            if cell.image_id and not cell.pixmap:
                load_start = time.time()
                pixmap = self._image_cache.get_pixmap(
                    cell.image_id,
                    max_size=(cell.rect.width(), cell.rect.height()),
                    use_thumbnail=True  # Use thumbnails for fast loading
                )
                if pixmap:
                    cell.pixmap = pixmap
                    loaded_count += 1
                    logger.debug("[IMGUR] Loaded pixmap for %s in %.3fs (size=%dx%d)", 
                               cell.image_id, time.time() - load_start, pixmap.width(), pixmap.height())
        
        logger.info("[IMGUR] Loaded %d pixmaps in %.3fs", loaded_count, time.time() - start_time)
        
        # Update UI on main thread
        if loaded_count > 0:
            ThreadManager.run_on_ui_thread(self._on_pixmaps_loaded)
    
    def _on_pixmaps_loaded(self) -> None:
        """Called on UI thread after pixmaps loaded in background."""
        if not Shiboken.isValid(self):
            return
        self._invalidate_cache()
        self.update()
        logger.debug("[IMGUR] Pixmaps loaded from background thread")
    
    def _refresh_grid_from_cache(self) -> None:
        """Refresh grid cell pixmaps from cache after downloads complete.
        
        Triggers background pixmap loading via ThreadManager.
        """
        if not Shiboken.isValid(self):
            return
        if not self._image_cache:
            return
        
        # Load pixmaps OFF UI thread
        if self._thread_manager:
            self._thread_manager.submit_io_task(self._load_pixmaps_background)
    
    def _invalidate_cache(self) -> None:
        """Invalidate the paint cache and cell pixmap cache."""
        self._cache_invalidated = True
        self._cached_pixmap = None
        self._cell_pixmap_cache.clear()
    
    def _regenerate_cache(self) -> None:
        """Regenerate the cached pixmap with proper DPR scaling (matches Reddit widget pattern)."""
        size = self.size()
        if size.isEmpty():
            return
        
        # Get device pixel ratio for crisp rendering (critical for high-DPI)
        try:
            dpr = self.devicePixelRatioF()
        except Exception:
            dpr = 1.0
        
        # Create DPR-aware pixmap (THIS IS THE KEY - must match Reddit widget)
        pixmap = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        try:
            self._paint_content(painter)
        finally:
            painter.end()
        
        self._cached_pixmap = pixmap
        self._cache_invalidated = False
    
    def paintEvent(self, event) -> None:
        """Paint the widget using cached pixmap."""
        with widget_paint_sample(self, "imgur.paint"):
            if self._cache_invalidated or self._cached_pixmap is None:
                self._regenerate_cache()
            
            if self._cached_pixmap:
                painter = QPainter(self)
                painter.drawPixmap(0, 0, self._cached_pixmap)
                painter.end()
    
    def _paint_content(self, painter: QPainter) -> None:
        """Paint widget content to painter."""
        # Draw background frame
        if self._show_background:
            self._paint_background(painter)
        
        # Draw header
        if self._show_header:
            self._paint_header(painter)
        
        # Draw image grid
        self._paint_grid(painter)
    
    def _paint_background(self, painter: QPainter) -> None:
        """Paint background frame."""
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        bg_color = QColor(self._bg_color)
        bg_color.setAlphaF(self._bg_opacity)
        
        border_color = QColor(self._border_color) if hasattr(self, '_border_color') else QColor(255, 255, 255, 80)
        
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 8, 8)
        
        painter.fillPath(path, bg_color)
        
        # Draw border if enabled (use border color with border opacity)
        if hasattr(self, '_border_color') and self._border_color.alpha() > 0:
            pen = QPen(border_color, 2)  # 2px border width
            painter.setPen(pen)
            painter.drawPath(path)
    
    def _paint_header(self, painter: QPainter) -> None:
        """Paint header with logo, tag name, and frame (matches Reddit widget pattern)."""
        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )
        
        # Header font setup (match Reddit widget)
        header_font = QFont(self._font_family, self._header_font_size, QFont.Weight.Bold)
        painter.setFont(header_font)
        header_metrics = QFontMetrics(header_font)
        header_top = rect.top() + 8  # +4px down from original
        baseline_y = header_top + header_metrics.ascent()
        
        # Draw header frame with shadow (match Reddit widget)
        self._paint_header_frame(painter, header_font, header_metrics, header_top)
        
        x = rect.left() + 15  # +12px right from original
        logo_size = max(0, int(self._header_font_size * 1.8))  # Scale logo with font
        
        # Draw logo (match Reddit widget pattern exactly)
        if self._header_logo is not None and not self._header_logo.isNull() and logo_size > 0:
            try:
                dpr = float(self.devicePixelRatioF())
            except Exception:
                dpr = 1.0
            scale_dpr = max(1.0, dpr)
            target_px = int(logo_size * scale_dpr)
            if target_px > 0:
                pm = self._header_logo.scaled(
                    target_px,
                    target_px,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                try:
                    pm.setDevicePixelRatio(scale_dpr)
                except Exception:
                    pass
                
                # Vertical center with header text (match Reddit)
                line_height = header_metrics.height()
                line_centre = header_top + (line_height * 0.6)
                icon_half = float(logo_size) / 2.0
                y_logo = int(line_centre - icon_half)
                if y_logo < header_top:
                    y_logo = header_top
                painter.drawPixmap(int(x), int(y_logo), pm)
            
            x += logo_size + 8
        else:
            x += 4
        
        # Draw header text with shadow (match Reddit widget)
        tag_display = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
        if tag_display == "most_viral":
            tag_display = "Most Viral"
        else:
            tag_display = tag_display.replace("_", " ").title()
        
        painter.setPen(QColor(255, 255, 255, 255))
        draw_text_with_shadow(painter, int(x), int(baseline_y), tag_display, font_size=self._header_font_size)
        
        # Store header hit rect for click handling
        header_text_width = header_metrics.horizontalAdvance(tag_display)
        header_height = header_metrics.height()
        header_width = (x - rect.left()) + header_text_width + 8
        self._header_hit_rect = QRect(
            rect.left(),
            header_top,
            min(int(header_width), rect.width()),
            header_height + 8,
        )
    
    def _paint_header_frame(self, painter: QPainter, header_font: QFont, header_metrics: QFontMetrics, header_top: int) -> None:
        """Paint header frame with shadow (matches Reddit widget pattern)."""
        if not self._show_background:
            return
        
        margins = self.contentsMargins()
        # Adjusted to match moved header: +12px right, +4px down from original
        left = margins.left() + 8  # Was -4, now +8 (+12px shift)
        top = margins.top() + 6    # Was +2, now +6 (+4px shift)
        
        # Calculate frame size from content
        logo_size = max(0, int(self._header_font_size * 1.8))
        tag_display = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
        if tag_display == "most_viral":
            tag_display = "Most Viral"
        else:
            tag_display = tag_display.replace("_", " ").title()
        
        text_w = header_metrics.horizontalAdvance(tag_display)
        text_h = header_metrics.height()
        gap = 8
        pad_x = 8
        pad_y = 4
        
        inner_w = logo_size + gap + text_w
        row_h = max(text_h, logo_size)
        total_w = int(inner_w + pad_x * 2)
        total_h = int(row_h + pad_y * 2)
        
        rect = QRect(left, top, total_w, total_h)
        radius = min(self._bg_corner_radius + 1 if hasattr(self, '_bg_corner_radius') else 7, 
                     min(rect.width(), rect.height()) / 2)
        
        # Use shadow helper for border with drop shadow (match Reddit widget)
        border_color = self._border_color if hasattr(self, '_border_color') else QColor(255, 255, 255, 255)
        border_width = max(1, self._bg_border_width) if hasattr(self, '_bg_border_width') else 3
        draw_rounded_rect_with_shadow(painter, rect, radius, border_color, border_width)
    
    def _paint_grid(self, painter: QPainter) -> None:
        """Paint the image grid."""
        with self._state_lock:
            cells = list(self._grid_cells)
        
        for cell in cells:
            self._paint_cell(painter, cell)
    
    def _paint_cell(self, painter: QPainter, cell: GridCell) -> None:
        """Paint a single grid cell (cache pixmap is already DPR-aware, use logical coords)."""
        rect = cell.rect
        
        # Draw cell background
        bg_color = QColor(60, 60, 60, 200)
        
        if self._image_border_radius > 0:
            path = QPainterPath()
            path.addRoundedRect(
                rect.x(), rect.y(), rect.width(), rect.height(),
                self._image_border_radius, self._image_border_radius
            )
            painter.fillPath(path, bg_color)
        else:
            painter.fillRect(rect, bg_color)
        
        # Draw image (painter is already in DPR-scaled pixmap, use logical coords)
        if cell.pixmap and not cell.pixmap.isNull():
            cell_size = (rect.width(), rect.height())
            cache_key = f"{cell.image_id}_{cell_size[0]}x{cell_size[1]}"
            
            # Check if cell size changed - invalidate cache
            if self._cell_cache_size != cell_size:
                self._cell_pixmap_cache.clear()
                self._cell_cache_size = cell_size
            
            # Get or create cached scaled pixmap (logical size, Qt handles DPR)
            if cache_key in self._cell_pixmap_cache:
                scaled = self._cell_pixmap_cache[cache_key]
            else:
                # Scale pixmap to fill cell (crop if needed)
                scaled = cell.pixmap.scaled(
                    rect.width(), rect.height(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                # Cache it (limit cache size)
                if len(self._cell_pixmap_cache) < 50:
                    self._cell_pixmap_cache[cache_key] = scaled
            
            # Center crop
            src_x = (scaled.width() - rect.width()) // 2
            src_y = (scaled.height() - rect.height()) // 2
            src_rect = QRect(src_x, src_y, rect.width(), rect.height())
            
            # Clip to rounded rect if needed
            if self._image_border_radius > 0:
                painter.save()
                path = QPainterPath()
                path.addRoundedRect(
                    rect.x(), rect.y(), rect.width(), rect.height(),
                    self._image_border_radius, self._image_border_radius
                )
                painter.setClipPath(path)
                painter.drawPixmap(rect.topLeft(), scaled, src_rect)
                painter.restore()
            else:
                painter.drawPixmap(rect.topLeft(), scaled, src_rect)
        
        # Draw border
        if self._image_border_enabled and self._image_border_width > 0:
            pen = QPen(self._image_border_color, self._image_border_width)
            painter.setPen(pen)
            
            if self._image_border_radius > 0:
                painter.drawRoundedRect(
                    rect.adjusted(1, 1, -1, -1),
                    self._image_border_radius, self._image_border_radius
                )
            else:
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
    
    def handle_click(self, pos: QPoint):
        """Handle click at position. Returns URL string for deferred opening via helper.
        
        The URL is stored in _pending_reddit_url and opened after screensaver exits
        using the Windows session-aware helper (launch_url_via_user_desktop).
        This prevents crashes when screensaver process tries to open URLs directly.
        """
        if not self._click_opens_browser:
            return False
        
        # Check header
        if self._header_hit_rect and self._header_hit_rect.contains(pos):
            tag = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
            if tag == "most_viral":
                url = "https://imgur.com/hot"
            else:
                url = f"https://imgur.com/t/{tag}"
            logger.info("[IMGUR] Header clicked, will open after exit: %s", url)
            return url
        
        # Check cells
        for rect, gallery_url in self._cell_hit_rects:
            if rect.contains(pos) and gallery_url:
                logger.info("[IMGUR] Cell clicked, will open after exit: %s", gallery_url)
                return gallery_url
        
        return False
    
    def set_tag(self, tag: str) -> None:
        """Set the Imgur tag to display."""
        if self._tag != tag:
            self._tag = tag
            self._fetch_images()
    
    def set_custom_tag(self, tag: str) -> None:
        """Set custom tag value."""
        self._custom_tag = tag
        if self._tag == "custom":
            self._fetch_images()
    
    def set_grid_rows(self, rows: int) -> None:
        """Set number of grid rows."""
        rows = max(1, min(6, rows))
        if self._grid_rows != rows:
            self._grid_rows = rows
            self._calculate_size()
            self._rebuild_grid()
            self._invalidate_cache()
            self.update()
    
    def set_grid_columns(self, cols: int) -> None:
        """Set number of grid columns."""
        cols = max(1, min(8, cols))
        if self._grid_cols != cols:
            self._grid_cols = cols
            self._calculate_size()
            self._rebuild_grid()
            self._invalidate_cache()
            self.update()
    
    def set_layout_mode(self, mode: str) -> None:
        """Set layout mode (vertical, square, hybrid)."""
        try:
            new_mode = LayoutMode(mode.lower())
            if self._layout_mode != new_mode:
                self._layout_mode = new_mode
                self._calculate_size()
                self._rebuild_grid()
                self._invalidate_cache()
                self.update()
        except ValueError:
            logger.warning("[IMGUR] Invalid layout mode: %s", mode)
    
    def set_image_spacing(self, spacing: int) -> None:
        """Set spacing between images."""
        spacing = max(0, min(20, spacing))
        if self._image_spacing != spacing:
            self._image_spacing = spacing
            self._calculate_size()
            self._rebuild_grid()
            self._invalidate_cache()
            self.update()
    
    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Fade the widget in using ShadowFadeProfile."""
        logger.debug("[IMGUR] _start_widget_fade_in: duration_ms=%s", duration_ms)
        
        if duration_ms <= 0:
            # Instant show without fade
            if self.parent():
                try:
                    self._update_position()
                except Exception as e:
                    logger.debug("[IMGUR] Exception suppressed: %s", e)
            try:
                self.show()
            except Exception as e:
                logger.debug("[IMGUR] Exception suppressed: %s", e)
            return
        
        # Update position before fade
        if self.parent():
            try:
                self._update_position()
            except Exception as e:
                logger.debug("[IMGUR] Exception suppressed: %s", e)
        
        # Show widget BEFORE starting fade animation so it's visible when fade begins
        # ShadowFadeProfile will handle the opacity animation
        try:
            self.show()
            logger.debug("[IMGUR] Widget shown before fade animation")
        except Exception as e:
            logger.debug("[IMGUR] Exception suppressed: %s", e)
        
        # WORKAROUND: Explicit raise needed because fade coordinator doesn't properly
        # raise Imgur widget like it does for Reddit/other widgets. Root cause unknown.
        # TODO: Investigate why raise_overlay() in transitions/overlay_manager.py doesn't
        # work for Imgur during fade coordinator's synchronized fade.
        try:
            self.raise_()
            logger.debug("[IMGUR] Widget raised above compositor")
        except Exception as e:
            logger.debug("[IMGUR] Exception suppressed: %s", e)
        
        # Fade in with shadow
        try:
            from widgets.shadow_utils import ShadowFadeProfile
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            logger.debug("[IMGUR] ShadowFadeProfile failed, showing instantly", exc_info=True)
            try:
                self.show()
            except Exception as e:
                logger.debug("[IMGUR] Exception suppressed: %s", e)
    
    def set_update_interval(self, seconds: int) -> None:
        """Set update interval in seconds."""
        seconds = max(300, min(3600, seconds))  # 5-60 minutes
        self._update_interval_sec = seconds
    
    def set_show_header(self, show: bool) -> None:
        """Set header visibility."""
        if self._show_header != show:
            self._show_header = show
            self._calculate_size()
            self._rebuild_grid()
            self._invalidate_cache()
            self.update()
    
    def set_image_border_enabled(self, enabled: bool) -> None:
        """Set image border visibility."""
        if self._image_border_enabled != enabled:
            self._image_border_enabled = enabled
            self._invalidate_cache()
            self.update()
    
    def set_image_border_width(self, width: int) -> None:
        """Set image border width."""
        width = max(0, min(5, width))
        if self._image_border_width != width:
            self._image_border_width = width
            self._invalidate_cache()
            self.update()
    
    def set_image_border_color(self, color: QColor) -> None:
        """Set image border color."""
        if self._image_border_color != color:
            self._image_border_color = color
            self._invalidate_cache()
            self.update()
    
    def set_image_border_radius(self, radius: int) -> None:
        """Set image border radius."""
        radius = max(0, min(20, radius))
        if self._image_border_radius != radius:
            self._image_border_radius = radius
            self._invalidate_cache()
            self.update()
    
    def set_click_opens_browser(self, enabled: bool) -> None:
        """Set whether clicks open browser."""
        self._click_opens_browser = enabled
    
    def get_cell_hit_rects(self) -> List[Tuple[QRect, str]]:
        """Get cell hit rectangles for click handling."""
        return list(self._cell_hit_rects)
    
    def get_header_hit_rect(self) -> Optional[QRect]:
        """Get header hit rectangle for click handling."""
        return self._header_hit_rect
