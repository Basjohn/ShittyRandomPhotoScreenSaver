"""Consolidated image loading utilities.

This module provides a unified interface for loading images across the codebase,
consolidating duplicate logic from screensaver_engine.py and image_prefetcher.py.

Section 3.4 Implementation: Consolidate duplicate image loading code.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtGui import QImage

from core.logging.logger import get_logger
from core.logging.tags import TAG_IMAGE
from core.constants import MIN_WALLPAPER_WIDTH, MIN_WALLPAPER_HEIGHT

logger = get_logger(__name__)


class ImageLoader:
    """Unified image loading interface."""
    
    @staticmethod
    def load_qimage(path: str, log_errors: bool = True) -> Optional[QImage]:
        """Load a QImage from disk.
        
        Args:
            path: Path to the image file
            log_errors: Whether to log errors (default True)
            
        Returns:
            QImage if successful, None if failed
        """
        try:
            img = QImage(path)
            if img.isNull():
                if log_errors:
                    logger.warning(f"{TAG_IMAGE} Failed to decode image: {path}")
                return None
            if img.width() < MIN_WALLPAPER_WIDTH or img.height() < MIN_WALLPAPER_HEIGHT:
                if log_errors:
                    logger.info(
                        "%s Skipping %s (too small: %sx%s)",
                        TAG_IMAGE,
                        path,
                        img.width(),
                        img.height(),
                    )
                return None
            return img
        except Exception as e:
            if log_errors:
                logger.exception(f"{TAG_IMAGE} Failed to load image {path}: {e}")
            return None
    
    @staticmethod
    def load_qimage_silent(path: str) -> Optional[QImage]:
        """Load a QImage from disk without logging errors.
        
        Useful for prefetch operations where failures are expected.
        
        Args:
            path: Path to the image file
            
        Returns:
            QImage if successful, None if failed
        """
        return ImageLoader.load_qimage(path, log_errors=False)
