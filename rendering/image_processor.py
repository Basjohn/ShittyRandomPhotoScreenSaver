"""
Image processing for screensaver display.

Handles scaling, cropping, and positioning of images for different display modes.
"""
from typing import Tuple
from PySide6.QtCore import Qt, QSize, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QImage
from rendering.display_modes import DisplayMode
from core.logging.logger import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """
    Process images for display on screen.
    
    Handles scaling, cropping, and positioning based on display mode.
    """
    
    @staticmethod
    def process_image(image: QPixmap, screen_size: QSize, 
                     mode: DisplayMode = DisplayMode.FILL) -> QPixmap:
        """
        Process image for display.
        
        Args:
            image: Source image (QPixmap)
            screen_size: Target screen size
            mode: Display mode (FILL, FIT, or SHRINK)
        
        Returns:
            Processed QPixmap ready for display
        """
        if image.isNull():
            logger.warning("[FALLBACK] Image is null, returning empty pixmap")
            return QPixmap(screen_size)
        
        if mode == DisplayMode.FILL:
            return ImageProcessor._process_fill(image, screen_size)
        elif mode == DisplayMode.FIT:
            return ImageProcessor._process_fit(image, screen_size)
        elif mode == DisplayMode.SHRINK:
            return ImageProcessor._process_shrink(image, screen_size)
        else:
            logger.error(f"Unknown display mode: {mode}, defaulting to FILL")
            return ImageProcessor._process_fill(image, screen_size)
    
    @staticmethod
    def _process_fill(image: QPixmap, screen_size: QSize) -> QPixmap:
        """
        FILL mode: Scale and crop to fill screen completely (no letterboxing).
        
        This is the PRIMARY display mode.
        
        Algorithm:
        1. Calculate aspect ratios
        2. Scale image to cover entire screen
        3. Crop excess if needed
        4. Center the result
        
        Args:
            image: Source image
            screen_size: Target screen size
        
        Returns:
            Processed pixmap that fills screen completely
        """
        img_size = image.size()
        
        # Calculate aspect ratios
        screen_ratio = screen_size.width() / screen_size.height()
        img_ratio = img_size.width() / img_size.height()
        
        # Determine scaling to fill screen
        if img_ratio > screen_ratio:
            # Image is wider - scale to height, crop width
            scale_height = screen_size.height()
            scale_width = int(scale_height * img_ratio)
        else:
            # Image is taller - scale to width, crop height
            scale_width = screen_size.width()
            scale_height = int(scale_width / img_ratio)
        
        # Scale image
        scaled = image.scaled(
            scale_width,
            scale_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # If scaled image is larger than screen, crop it
        if scaled.width() > screen_size.width() or scaled.height() > screen_size.height():
            # Calculate crop position (center)
            x_offset = (scaled.width() - screen_size.width()) // 2
            y_offset = (scaled.height() - screen_size.height()) // 2
            
            # Create output pixmap
            result = QPixmap(screen_size)
            result.fill(Qt.GlobalColor.black)
            
            # Draw cropped portion
            painter = QPainter(result)
            painter.drawPixmap(
                0, 0,  # Destination
                scaled,
                x_offset, y_offset,  # Source crop
                screen_size.width(), screen_size.height()  # Crop size
            )
            painter.end()
            
            logger.debug(f"FILL: Scaled to {scaled.width()}x{scaled.height()}, "
                        f"cropped from ({x_offset},{y_offset})")
            return result
        else:
            # Scaled image fits exactly
            logger.debug(f"FILL: Scaled to {scaled.width()}x{scaled.height()} (perfect fit)")
            return scaled
    
    @staticmethod
    def _process_fit(image: QPixmap, screen_size: QSize) -> QPixmap:
        """
        FIT mode: Scale to fit within screen (may have letterboxing/pillarboxing).
        
        Algorithm:
        1. Scale image to fit within screen bounds
        2. Maintain aspect ratio
        3. Center on black background
        
        Args:
            image: Source image
            screen_size: Target screen size
        
        Returns:
            Processed pixmap with letterboxing if needed
        """
        # Scale to fit within screen
        scaled = image.scaled(
            screen_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Create output with black background
        result = QPixmap(screen_size)
        result.fill(Qt.GlobalColor.black)
        
        # Center scaled image
        x_offset = (screen_size.width() - scaled.width()) // 2
        y_offset = (screen_size.height() - scaled.height()) // 2
        
        painter = QPainter(result)
        painter.drawPixmap(x_offset, y_offset, scaled)
        painter.end()
        
        logger.debug(f"FIT: Scaled to {scaled.width()}x{scaled.height()}, "
                    f"centered at ({x_offset},{y_offset})")
        return result
    
    @staticmethod
    def _process_shrink(image: QPixmap, screen_size: QSize) -> QPixmap:
        """
        SHRINK mode: Only scale down if larger than screen, never upscale.
        
        Algorithm:
        1. If image is larger than screen, scale down to fit
        2. If image is smaller, keep original size
        3. Center on black background
        
        Args:
            image: Source image
            screen_size: Target screen size
        
        Returns:
            Processed pixmap (never upscaled)
        """
        img_size = image.size()
        
        # Check if scaling is needed
        if img_size.width() <= screen_size.width() and img_size.height() <= screen_size.height():
            # Image is smaller than screen - use original size
            result = QPixmap(screen_size)
            result.fill(Qt.GlobalColor.black)
            
            # Center original image
            x_offset = (screen_size.width() - img_size.width()) // 2
            y_offset = (screen_size.height() - img_size.height()) // 2
            
            painter = QPainter(result)
            painter.drawPixmap(x_offset, y_offset, image)
            painter.end()
            
            logger.debug(f"SHRINK: Original size {img_size.width()}x{img_size.height()}, "
                        f"centered at ({x_offset},{y_offset})")
            return result
        else:
            # Image is larger - scale down to fit
            scaled = image.scaled(
                screen_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Create output with black background
            result = QPixmap(screen_size)
            result.fill(Qt.GlobalColor.black)
            
            # Center scaled image
            x_offset = (screen_size.width() - scaled.width()) // 2
            y_offset = (screen_size.height() - scaled.height()) // 2
            
            painter = QPainter(result)
            painter.drawPixmap(x_offset, y_offset, scaled)
            painter.end()
            
            logger.debug(f"SHRINK: Scaled down to {scaled.width()}x{scaled.height()}, "
                        f"centered at ({x_offset},{y_offset})")
            return result
    
    @staticmethod
    def calculate_scale_factors(source_size: QSize, target_size: QSize, 
                                mode: DisplayMode) -> Tuple[float, float]:
        """
        Calculate scale factors for a given display mode.
        
        Useful for debugging and pan & scan calculations.
        
        Args:
            source_size: Original image size
            target_size: Target screen size
            mode: Display mode
        
        Returns:
            Tuple of (scale_x, scale_y) factors
        """
        if mode == DisplayMode.FILL:
            # Scale to cover screen
            screen_ratio = target_size.width() / target_size.height()
            img_ratio = source_size.width() / source_size.height()
            
            if img_ratio > screen_ratio:
                # Scale by height
                scale = target_size.height() / source_size.height()
            else:
                # Scale by width
                scale = target_size.width() / source_size.width()
            
            return (scale, scale)
        
        elif mode == DisplayMode.FIT:
            # Scale to fit within screen
            scale_x = target_size.width() / source_size.width()
            scale_y = target_size.height() / source_size.height()
            scale = min(scale_x, scale_y)
            return (scale, scale)
        
        elif mode == DisplayMode.SHRINK:
            # Only scale down
            if source_size.width() <= target_size.width() and \
               source_size.height() <= target_size.height():
                return (1.0, 1.0)  # No scaling
            else:
                # Scale down to fit
                scale_x = target_size.width() / source_size.width()
                scale_y = target_size.height() / source_size.height()
                scale = min(scale_x, scale_y)
                return (scale, scale)
        
        return (1.0, 1.0)
    
    @staticmethod
    def get_crop_rect(source_size: QSize, target_size: QSize) -> QRect:
        """
        Calculate crop rectangle for FILL mode.
        
        Args:
            source_size: Scaled image size
            target_size: Target screen size
        
        Returns:
            QRect defining crop area
        """
        x_offset = (source_size.width() - target_size.width()) // 2
        y_offset = (source_size.height() - target_size.height()) // 2
        
        return QRect(
            max(0, x_offset),
            max(0, y_offset),
            min(target_size.width(), source_size.width()),
            min(target_size.height(), source_size.height())
        )
