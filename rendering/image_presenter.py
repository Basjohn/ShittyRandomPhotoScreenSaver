"""
Image Presenter - Extracted from DisplayWidget for better separation of concerns.

Manages image loading, processing, and pixmap lifecycle for display.

Phase E Context: This module centralizes pixmap management to ensure consistent
state during transitions and avoid stale pixmap references.
"""
from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Signal, QObject, QSize
from PySide6.QtGui import QPixmap

from core.logging.logger import get_logger, is_verbose_logging
from rendering.display_modes import DisplayMode
from rendering.image_processor import ImageProcessor

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget

logger = get_logger(__name__)


def _describe_pixmap(pm: Optional[QPixmap]) -> str:
    """Describe a pixmap for logging."""
    if pm is None:
        return "None"
    try:
        if pm.isNull():
            return "NullPixmap"
        size = pm.size()
        return (
            f"Pixmap(id={id(pm):#x}, cacheKey={pm.cacheKey():#x}, "
            f"size={size.width()}x{size.height()}, dpr={pm.devicePixelRatio():.2f})"
        )
    except Exception:
        return "Pixmap(?)"


class ImagePresenter(QObject):
    """
    Manages image loading and pixmap lifecycle for DisplayWidget.
    
    Responsibilities:
    - Image processing with display modes
    - Pixmap caching and lifecycle
    - Device pixel ratio handling
    - Seed pixmap management for transition smoothness
    
    Phase E Context:
        This class provides consistent pixmap state management,
        ensuring transitions always have valid source/destination pixmaps.
    """
    
    # Signals
    image_ready = Signal(QPixmap, str)  # processed_pixmap, image_path
    image_error = Signal(str)  # error_message
    
    def __init__(
        self,
        parent: "DisplayWidget",
        display_mode: DisplayMode = DisplayMode.FIT,
        device_pixel_ratio: float = 1.0,
    ):
        """
        Initialize the ImagePresenter.
        
        Args:
            parent: The DisplayWidget that owns this presenter
            display_mode: Initial display mode for image processing
            device_pixel_ratio: DPI scaling factor
        """
        super().__init__(parent)
        self._parent = parent
        self._display_mode = display_mode
        self._device_pixel_ratio = device_pixel_ratio
        
        # Pixmap state
        self._current_pixmap: Optional[QPixmap] = None
        self._previous_pixmap: Optional[QPixmap] = None
        self._seed_pixmap: Optional[QPixmap] = None
        self._last_seed_ts: Optional[float] = None
        
        # Image processor
        self._processor = ImageProcessor()
        
        logger.debug("[IMAGE_PRESENTER] Initialized with mode=%s, dpr=%.2f",
                     display_mode, device_pixel_ratio)
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def current_pixmap(self) -> Optional[QPixmap]:
        """Get the current displayed pixmap."""
        return self._current_pixmap
    
    @current_pixmap.setter
    def current_pixmap(self, value: Optional[QPixmap]) -> None:
        """Set the current displayed pixmap."""
        self._current_pixmap = value
    
    @property
    def previous_pixmap(self) -> Optional[QPixmap]:
        """Get the previous pixmap (for transitions)."""
        return self._previous_pixmap
    
    @previous_pixmap.setter
    def previous_pixmap(self, value: Optional[QPixmap]) -> None:
        """Set the previous pixmap."""
        self._previous_pixmap = value
    
    @property
    def seed_pixmap(self) -> Optional[QPixmap]:
        """Get the seed pixmap for transition smoothness."""
        return self._seed_pixmap
    
    @property
    def display_mode(self) -> DisplayMode:
        """Get the current display mode."""
        return self._display_mode
    
    @display_mode.setter
    def display_mode(self, value: DisplayMode) -> None:
        """Set the display mode."""
        self._display_mode = value
    
    @property
    def device_pixel_ratio(self) -> float:
        """Get the device pixel ratio."""
        return self._device_pixel_ratio
    
    @device_pixel_ratio.setter
    def device_pixel_ratio(self, value: float) -> None:
        """Set the device pixel ratio."""
        self._device_pixel_ratio = value
    
    # =========================================================================
    # Image Processing
    # =========================================================================
    
    def process_image(
        self,
        pixmap: QPixmap,
        target_size: tuple[int, int],
        image_path: str = "",
    ) -> Optional[QPixmap]:
        """
        Process an image for display.
        
        Args:
            pixmap: The source pixmap to process
            target_size: Target (width, height) for processing
            image_path: Path to the image (for logging)
            
        Returns:
            Processed pixmap or None on error
        """
        if pixmap is None or pixmap.isNull():
            logger.warning("[IMAGE_PRESENTER] Received null pixmap")
            self.image_error.emit("Failed to load image")
            return None
        
        try:
            if isinstance(target_size, tuple):
                width, height = target_size
                target_qsize = QSize(int(width), int(height))
            elif isinstance(target_size, QSize):
                target_qsize = target_size
            else:
                try:
                    w = int(getattr(target_size, "width", lambda: 0)())
                    h = int(getattr(target_size, "height", lambda: 0)())
                    target_qsize = QSize(w, h)
                except Exception:
                    target_qsize = QSize(pixmap.width(), pixmap.height())

            processed = self._processor.process_image(
                pixmap, target_qsize, self._display_mode
            )
            
            if processed is None or processed.isNull():
                logger.warning("[IMAGE_PRESENTER] Processing returned null pixmap")
                self.image_error.emit("Failed to process image")
                return None
            
            # Apply device pixel ratio
            try:
                processed.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
            
            if is_verbose_logging():
                logger.debug(
                    "[IMAGE_PRESENTER] Processed: %s -> %s",
                    _describe_pixmap(pixmap),
                    _describe_pixmap(processed),
                )
            
            return processed
            
        except Exception as e:
            logger.error("[IMAGE_PRESENTER] Processing failed: %s", e, exc_info=True)
            self.image_error.emit(f"Failed to process image: {e}")
            return None
    
    # =========================================================================
    # Pixmap Lifecycle
    # =========================================================================
    
    def set_current(self, pixmap: QPixmap, update_seed: bool = True) -> None:
        """
        Set the current pixmap.
        
        Args:
            pixmap: The new current pixmap
            update_seed: Whether to also update the seed pixmap
        """
        self._current_pixmap = pixmap
        
        if pixmap:
            try:
                pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
        
        if update_seed and pixmap:
            self._seed_pixmap = pixmap
            self._last_seed_ts = time.monotonic()
            
            if is_verbose_logging():
                logger.debug(
                    "[IMAGE_PRESENTER] Seed pixmap set: %s",
                    _describe_pixmap(pixmap),
                )
    
    def prepare_for_transition(self) -> QPixmap:
        """
        Prepare pixmaps for a transition.
        
        Caches the current pixmap as previous and returns it.
        
        Returns:
            The previous pixmap reference for the transition
        """
        previous_ref = self._current_pixmap
        return previous_ref
    
    def complete_transition(self, new_pixmap: QPixmap, pan_preview: Optional[QPixmap] = None) -> None:
        """
        Complete a transition by updating pixmap state.
        
        Args:
            new_pixmap: The new pixmap to display
            pan_preview: Optional pan preview frame
        """
        self._current_pixmap = pan_preview or new_pixmap
        
        if self._current_pixmap:
            try:
                self._current_pixmap.setDevicePixelRatio(self._device_pixel_ratio)
            except Exception:
                pass
        
        self._seed_pixmap = self._current_pixmap
        self._last_seed_ts = time.monotonic()
        self._previous_pixmap = None
        
        if is_verbose_logging():
            logger.debug(
                "[IMAGE_PRESENTER] Transition complete, seed: %s",
                _describe_pixmap(self._current_pixmap),
            )
    
    def clear(self) -> None:
        """Clear all pixmap state."""
        self._previous_pixmap = self._current_pixmap
        self._current_pixmap = None
        self._seed_pixmap = None
        self._last_seed_ts = None
    
    def show_error(self, message: str) -> None:
        """Set error state and clear current pixmap."""
        self._previous_pixmap = self._current_pixmap
        self._current_pixmap = None
        self._seed_pixmap = None
        self._last_seed_ts = None
        self.image_error.emit(message)
    
    # =========================================================================
    # Seed Pixmap for Wallpaper Capture
    # =========================================================================
    
    def seed_from_screen(self, screen) -> bool:
        """
        Seed the presenter with a capture of the current screen.
        
        Args:
            screen: QScreen to capture from
            
        Returns:
            True if seeding succeeded
        """
        try:
            wallpaper_pm = screen.grabWindow(0)
            if wallpaper_pm is not None and not wallpaper_pm.isNull():
                try:
                    wallpaper_pm.setDevicePixelRatio(self._device_pixel_ratio)
                except Exception:
                    pass
                self._current_pixmap = wallpaper_pm
                self._previous_pixmap = wallpaper_pm
                self._seed_pixmap = wallpaper_pm
                self._last_seed_ts = time.monotonic()
                return True
        except Exception:
            pass
        return False
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup(self) -> None:
        """Clean up all pixmap state."""
        self._current_pixmap = None
        self._previous_pixmap = None
        self._seed_pixmap = None
        self._last_seed_ts = None
        logger.debug("[IMAGE_PRESENTER] Cleanup complete")
