"""
Image processing for screensaver display.

Handles scaling, cropping, and positioning of images for different display modes.
"""
from typing import Tuple
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QImage
from rendering.display_modes import DisplayMode
from core.logging.logger import get_logger
from rendering.image_processor_async import AsyncImageProcessor

logger = get_logger(__name__)

try:
    from PIL import Image, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("PIL/Pillow not available, using Qt scaling only")


class ImageProcessor:
    """
    Process images for display on screen.
    
    Handles scaling, cropping, and positioning based on display mode.
    """
    
    @staticmethod
    def process_image(image: QPixmap, screen_size: QSize, 
                     mode: DisplayMode = DisplayMode.FILL,
                     use_lanczos: bool = False,
                     sharpen: bool = False) -> QPixmap:
        """Process image for display.

        This is now a thin wrapper around the QImage-first implementation in
        ``AsyncImageProcessor`` so the crop/scale logic is shared between
        sync/async paths. All heavy work happens on ``QImage``; this wrapper
        simply converts to/from ``QPixmap`` for existing callers.
        """

        if image.isNull():
            logger.warning("[FALLBACK] Image is null, delegating to QImage path")

        qimage = image.toImage()
        processed_qimage = AsyncImageProcessor.process_qimage(
            qimage,
            screen_size,
            mode,
            use_lanczos,
            sharpen,
        )
        return QPixmap.fromImage(processed_qimage)
    
    @staticmethod
    def _scale_pixmap(pixmap: QPixmap, width: int, height: int, use_lanczos: bool = False, sharpen: bool = False) -> QPixmap:
        """
        Scale a pixmap using PIL Lanczos (if available) or Qt.
        
        Args:
            pixmap: Source pixmap
            width: Target width
            height: Target height
            use_lanczos: Use PIL Lanczos resampling
            sharpen: Apply sharpening filter
        
        Returns:
            Scaled pixmap
        """
        # If PIL not available or Lanczos disabled, use Qt
        if not PILLOW_AVAILABLE or not use_lanczos:
            return pixmap.scaled(
                width, height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        try:
            # Convert QPixmap to PIL Image
            qimage = pixmap.toImage()
            
            # Convert to RGB888 or RGBA8888 format for PIL
            if qimage.hasAlphaChannel():
                qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
                mode = 'RGBA'
            else:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
                mode = 'RGB'
            # Get image data - handle both sip.voidptr and memoryview
            ptr = qimage.constBits()
            if hasattr(ptr, 'setsize'):
                # sip.voidptr (older PySide6 versions)
                ptr.setsize(qimage.sizeInBytes())
                img_data = bytes(ptr)
            else:
                # memoryview (newer PySide6 versions)
                img_data = ptr.tobytes()
            
            # Create PIL Image from buffer
            pil_image = Image.frombytes(
                mode,
                (qimage.width(), qimage.height()),
                img_data
            )
            
            # Scale with Lanczos
            scaled_pil = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            
            # Apply sharpening if requested and downscaling
            # Use stronger sharpening for aggressive downscaling
            if sharpen and (width < qimage.width() or height < qimage.height()):
                scale_factor = min(width / qimage.width(), height / qimage.height())
                if scale_factor < 0.5:  # Aggressive downscaling (>2x)
                    # Use UnsharpMask for better quality on aggressive downscaling
                    # FIX: Import moved to top of file
                    scaled_pil = scaled_pil.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
                else:
                    # Regular sharpening for moderate downscaling
                    scaled_pil = scaled_pil.filter(ImageFilter.SHARPEN)
            
            # Convert back to QPixmap
            if scaled_pil.mode == 'RGBA':
                data = scaled_pil.tobytes('raw', 'RGBA')
                qimg = QImage(
                    data,
                    scaled_pil.width,
                    scaled_pil.height,
                    scaled_pil.width * 4,
                    QImage.Format.Format_RGBA8888,
                )
                # Critical: convert to premultiplied for correct blending in Qt
                qimg = qimg.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            else:
                data = scaled_pil.tobytes('raw', 'RGB')
                qimg = QImage(
                    data,
                    scaled_pil.width,
                    scaled_pil.height,
                    scaled_pil.width * 3,
                    QImage.Format.Format_RGB888,
                )
            
            result = QPixmap.fromImage(qimg)
            logger.debug(f"Scaled with Lanczos: {pixmap.width()}x{pixmap.height()} → {width}x{height}")
            return result
        
        except Exception as e:
            logger.warning(f"Lanczos scaling failed, falling back to Qt: {e}")
            return pixmap.scaled(
                width, height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
    
    @staticmethod
    def _process_fill(image: QPixmap, screen_size: QSize, use_lanczos: bool = True, sharpen: bool = False) -> QPixmap:
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
        
        # FIX: Validate dimensions to prevent division by zero
        if screen_size.height() == 0 or img_size.height() == 0:
            logger.error(f"Invalid dimensions: screen={screen_size.width()}x{screen_size.height()}, img={img_size.width()}x{img_size.height()}")
            return QPixmap(screen_size)
        
        # Calculate aspect ratios
        screen_ratio = screen_size.width() / screen_size.height()
        img_ratio = img_size.width() / img_size.height()
        
        # Determine scaling to fill screen completely
        # Always scale to ensure full coverage with no black bars
        if img_ratio > screen_ratio:
            # Image is wider - scale to height, crop width
            scale_height = screen_size.height()
            scale_width = int(scale_height * img_ratio)
        else:
            # Image is taller - scale to width, crop height
            scale_width = screen_size.width()
            scale_height = int(scale_width / img_ratio)
        
        # Ensure we always have at least screen size (never smaller)
        scale_width = max(scale_width, screen_size.width())
        scale_height = max(scale_height, screen_size.height())
        
        # ALWAYS scale with Lanczos when needed for best quality
        # Even when downsampling - Lanczos provides superior quality
        if scale_width == img_size.width() and scale_height == img_size.height():
            # Exact size match - no scaling needed
            scaled = image
            logger.debug(f"Fill: Exact size match {img_size.width()}x{img_size.height()}, no scaling")
        else:
            # Scale required (up or down) - use Lanczos for quality
            scaled = ImageProcessor._scale_pixmap(
                image, scale_width, scale_height, use_lanczos, sharpen
            )
            logger.debug(f"Fill: Scaled {img_size.width()}x{img_size.height()} → {scale_width}x{scale_height} (Lanczos={use_lanczos})")
        
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
            
            logger.info(f"FILL: Image {img_size.width()}x{img_size.height()} → "
                       f"scaled {scaled.width()}x{scaled.height()} → "
                       f"cropped to {screen_size.width()}x{screen_size.height()}")
            return result
        else:
            # Scaled image fits exactly
            logger.info(f"FILL: Image {img_size.width()}x{img_size.height()} → "
                       f"{scaled.width()}x{scaled.height()} (perfect fit)")
            return scaled
    
    @staticmethod
    def _process_fit(image: QPixmap, screen_size: QSize, use_lanczos: bool = True, sharpen: bool = False) -> QPixmap:
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
        # Get image dimensions
        # FIX: Validate dimensions to prevent division by zero
        if image.height() == 0 or screen_size.height() == 0:
            logger.error(f"Invalid dimensions for fit: screen={screen_size.width()}x{screen_size.height()}, img={image.width()}x{image.height()}")
            return QPixmap(screen_size)
        
        img_ratio = image.width() / image.height()
        screen_ratio = screen_size.width() / screen_size.height()
        
        if img_ratio > screen_ratio:
            # Image is wider - fit to width, add letterbox (black bars top/bottom)
            target_width = screen_size.width()
            target_height = int(target_width / img_ratio)
        else:
            # Image is taller - fit to height, add pillarbox (black bars left/right)
            target_height = screen_size.height()
            target_width = int(target_height * img_ratio)
        
        # Ensure we maintain exact aspect ratio
        # This prevents any distortion
        actual_ratio = target_width / target_height
        if abs(actual_ratio - img_ratio) > 0.01:  # Check for rounding errors
            if img_ratio > screen_ratio:
                target_height = int(target_width / img_ratio)
            else:
                target_width = int(target_height * img_ratio)
        
        # Scale to fit within screen (with Lanczos if enabled)
        scaled = ImageProcessor._scale_pixmap(
            image, target_width, target_height, use_lanczos, sharpen
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
    def _process_shrink(image: QPixmap, screen_size: QSize, use_lanczos: bool = True, sharpen: bool = False) -> QPixmap:
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
        
        # FIX: Validate dimensions to prevent division by zero
        if img_size.height() == 0 or screen_size.height() == 0:
            logger.error(f"Invalid dimensions for shrink: screen={screen_size.width()}x{screen_size.height()}, img={img_size.width()}x{img_size.height()}")
            return QPixmap(screen_size)
        
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
            # Calculate target size maintaining aspect ratio
            img_ratio = img_size.width() / img_size.height()
            screen_ratio = screen_size.width() / screen_size.height()
            
            if img_ratio > screen_ratio:
                target_width = screen_size.width()
                target_height = int(target_width / img_ratio)
            else:
                target_height = screen_size.height()
                target_width = int(target_height * img_ratio)
            
            scaled = ImageProcessor._scale_pixmap(
                image, target_width, target_height, use_lanczos, sharpen
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
