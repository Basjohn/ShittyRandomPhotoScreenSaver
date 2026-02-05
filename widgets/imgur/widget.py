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
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont,
    QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.performance import widget_paint_sample
from core.threading.manager import ThreadManager
from core.windows.url_launcher import launch_url_via_user_desktop
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
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
IMGUR_LOGO_PATH = Path(__file__).parent.parent.parent / "images" / "Imgur.png"


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
        
        # State (protected by locks)
        self._state_lock = threading.Lock()
        self._images: List[ImgurImage] = []
        self._grid_cells: List[GridCell] = []
        self._fetching = False
        self._last_fetch_time: float = 0.0
        self._fade_registered = False  # Track if fade sync has been requested
        
        # Paint caching
        self._cached_pixmap: Optional[QPixmap] = None
        self._cache_invalidated = True
        
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
        self._apply_base_styling()
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
    
    def _get_cell_height(self, cell_width: int) -> int:
        """Get cell height based on layout mode."""
        if self._layout_mode == LayoutMode.VERTICAL:
            return int(cell_width * 16 / 9)  # 9:16 aspect
        elif self._layout_mode == LayoutMode.SQUARE:
            return cell_width  # 1:1 aspect
        else:  # HYBRID
            return int(cell_width * 1.2)  # Slightly tall
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh display."""
        self._fetch_images()
    
    def _initialize_impl(self) -> None:
        """Initialize resources (lifecycle hook)."""
        # Create scraper and cache
        self._scraper = ImgurScraper()
        self._image_cache = ImgurImageCache()
        logger.debug("[LIFECYCLE] ImgurWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate widget - start fetching (lifecycle hook)."""
        if not self._ensure_thread_manager("ImgurWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
        # Load cached images first
        self._load_from_cache()
        
        # Schedule periodic updates with jitter
        self._schedule_timer()
        
        # Fetch fresh images
        self._fetch_images()
        
        logger.debug("[LIFECYCLE] ImgurWidget activated")
    
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
    
    def _load_from_cache(self) -> None:
        """Load images from disk cache for fast startup."""
        if not self._image_cache:
            return
        
        cached = self._image_cache.get_all_cached()
        if not cached:
            return
        
        # Take up to grid size images
        needed = self._grid_rows * self._grid_cols
        cached = cached[:needed]
        
        with self._state_lock:
            self._images = [
                ImgurImage(
                    id=c.id,
                    url=f"https://i.imgur.com/{c.id}l.jpg",
                    thumbnail_url=f"https://i.imgur.com/{c.id}t.jpg",
                    gallery_url=c.gallery_url,
                    is_animated=c.is_animated,
                )
                for c in cached
            ]
        
        self._rebuild_grid()
        self._invalidate_cache()
        
        logger.info("[IMGUR] Loaded %d images from cache", len(cached))
    
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
            
            # Update UI immediately with scraped images (don't wait for downloads)
            images_to_display = result.images[:needed]
            
            if images_to_display:
                logger.info("[IMGUR] Updating UI with %d scraped images", len(images_to_display))
                ThreadManager.run_on_ui_thread(
                    lambda: self._on_images_fetched(images_to_display)
                )
                
                # Download images to cache in background, refresh UI after each
                logger.debug("[IMGUR] Starting background download of %d images", len(images_to_display))
                for img in images_to_display:
                    if self._download_and_cache(img):
                        # Refresh grid on UI thread after each successful download
                        ThreadManager.run_on_ui_thread(self._refresh_grid_from_cache)
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
            return False
        
        # Check if already cached
        if self._image_cache.has(image.id):
            return True
        
        # Download image
        import requests
        from core.reddit_rate_limiter import get_reddit_user_agent
        
        try:
            response = requests.get(
                image.get_large_url(),
                headers={"User-Agent": get_reddit_user_agent()},
                timeout=10,
            )
            
            if response.status_code != 200:
                return False
            
            # Cache it
            cached = self._image_cache.put(
                image.id,
                response.content,
                extension=image.extension,
                is_animated=image.is_animated,
                gallery_url=image.gallery_url,
            )
            
            return cached is not None
            
        except Exception as e:
            logger.debug("[IMGUR] Download failed for %s: %s", image.id, e)
            return False
    
    def _on_images_fetched(self, images: List[ImgurImage]) -> None:
        """Handle fetched images (called on UI thread)."""
        with self._state_lock:
            self._images = images
            should_register_fade = not self._fade_registered and images
        
        self._rebuild_grid()
        self._invalidate_cache()
        self.update()
        
        logger.info("[IMGUR] Updated with %d images", len(images))
        
        # Fade coordination: register with parent on first fetch with images
        if should_register_fade:
            parent = self.parent()
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                def _starter() -> None:
                    try:
                        self._start_widget_fade_in(1500)
                    except Exception as e:
                        logger.debug("[IMGUR] Exception suppressed: %s", e)
                
                try:
                    overlay_name = getattr(self, '_overlay_name', 'imgur')
                    parent.request_overlay_fade_sync(overlay_name, _starter)
                    with self._state_lock:
                        self._fade_registered = True
                    logger.debug("[IMGUR] Fade sync requested")
                except Exception as e:
                    logger.debug("[IMGUR] Exception suppressed: %s", e)
                    _starter()
            else:
                # No fade coordinator - just fade in directly
                try:
                    self._start_widget_fade_in(1500)
                    with self._state_lock:
                        self._fade_registered = True
                except Exception as e:
                    logger.debug("[IMGUR] Exception suppressed: %s", e)
    
    def _rebuild_grid(self) -> None:
        """Rebuild the grid cell layout."""
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
        
        # Build cells
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
                    
                    # Load pixmap from cache
                    if self._image_cache:
                        cell.pixmap = self._image_cache.get_pixmap(
                            img.id,
                            max_size=(cell_width, cell_height)
                        )
                    
                    self._cell_hit_rects.append((rect, img.gallery_url))
                
                cells.append(cell)
        
        with self._state_lock:
            self._grid_cells = cells
    
    def _refresh_grid_from_cache(self) -> None:
        """Refresh grid cell pixmaps from cache after downloads complete."""
        if not self._image_cache:
            return
        
        with self._state_lock:
            cells = self._grid_cells
            for cell in cells:
                if cell.image_id and (cell.pixmap is None or cell.pixmap.isNull()):
                    cell.pixmap = self._image_cache.get_pixmap(
                        cell.image_id,
                        max_size=(cell.rect.width(), cell.rect.height())
                    )
        
        self._invalidate_cache()
        self.update()
    
    def _invalidate_cache(self) -> None:
        """Invalidate the paint cache."""
        self._cache_invalidated = True
        self._cached_pixmap = None
    
    def _regenerate_cache(self) -> None:
        """Regenerate the cached pixmap."""
        size = self.size()
        if size.isEmpty():
            return
        
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
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
        
        if self._border_width > 0:
            pen = QPen(border_color, self._border_width)
            painter.setPen(pen)
            painter.drawPath(path)
    
    def _paint_header(self, painter: QPainter) -> None:
        """Paint header with logo and tag name."""
        padding = 10
        y = padding
        
        # Header background
        header_rect = QRect(padding, y, self.width() - padding * 2, HEADER_HEIGHT)
        self._header_hit_rect = header_rect
        
        # Draw logo
        logo_size = HEADER_HEIGHT - 8
        logo_x = padding + 4
        logo_y = y + 4
        
        if self._header_logo and not self._header_logo.isNull():
            scaled_logo = self._header_logo.scaled(
                logo_size, logo_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(logo_x, logo_y, scaled_logo)
        
        # Draw tag text
        text_x = logo_x + logo_size + 8
        text_rect = QRect(text_x, y, header_rect.width() - text_x, HEADER_HEIGHT)
        
        font = QFont(self._font_family, self._header_font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(self._text_color)
        
        tag_display = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
        if tag_display == "most_viral":
            tag_display = "Most Viral"
        else:
            tag_display = f"#{tag_display}"
        
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, tag_display)
    
    def _paint_grid(self, painter: QPainter) -> None:
        """Paint the image grid."""
        with self._state_lock:
            cells = list(self._grid_cells)
        
        for cell in cells:
            self._paint_cell(painter, cell)
    
    def _paint_cell(self, painter: QPainter, cell: GridCell) -> None:
        """Paint a single grid cell."""
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
        
        # Draw image
        if cell.pixmap and not cell.pixmap.isNull():
            # Scale pixmap to fill cell (crop if needed)
            scaled = cell.pixmap.scaled(
                rect.width(), rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            
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
    
    def handle_click(self, pos: QPoint) -> bool:
        """Handle click at position. Returns True if click was handled."""
        if not self._click_opens_browser:
            return False
        
        # Check header
        if self._header_hit_rect and self._header_hit_rect.contains(pos):
            tag = self._custom_tag if self._tag == "custom" and self._custom_tag else self._tag
            if tag == "most_viral":
                url = "https://imgur.com/hot"
            else:
                url = f"https://imgur.com/t/{tag}"
            launch_url_via_user_desktop(url)
            return True
        
        # Check cells
        for rect, gallery_url in self._cell_hit_rects:
            if rect.contains(pos) and gallery_url:
                launch_url_via_user_desktop(gallery_url)
                return True
        
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
