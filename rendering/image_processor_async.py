"""Async/QImage-based image processing helpers.

Optional further-async path for the image pipeline. This module mirrors the
behaviour of ``rendering.image_processor.ImageProcessor`` but operates on
``QImage`` instead of ``QPixmap`` and is safe to run on ThreadManager's
COMPUTE pool.
"""
from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QImage

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager, TaskResult
from rendering.display_modes import DisplayMode


logger = get_logger(__name__)

try:
    from PIL import Image, ImageFilter  # type: ignore[import]

    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    PILLOW_AVAILABLE = False
    logger.warning("PIL/Pillow not available, using Qt scaling only (async path)")


class AsyncImageProcessor:
    """QImage-first image processing utilities.

    These helpers are intended for use on the COMPUTE pool. They avoid
    ``QPixmap`` entirely so they are safe to call off the GUI thread.
    """

    @staticmethod
    def process_qimage(
        image: QImage,
        screen_size: QSize,
        mode: DisplayMode = DisplayMode.FILL,
        use_lanczos: bool = False,
        sharpen: bool = False,
    ) -> QImage:
        """Synchronous QImage processing that mirrors ImageProcessor.process_image.

        Returns a QImage cropped/scaled to ``screen_size`` according to ``mode``.
        """

        if image.isNull():
            logger.warning("[FALLBACK] QImage is null, returning empty ARGB32 image")
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)
            return result

        if mode == DisplayMode.FILL:
            return AsyncImageProcessor._process_fill_qimage(
                image, screen_size, use_lanczos, sharpen
            )
        if mode == DisplayMode.FIT:
            return AsyncImageProcessor._process_fit_qimage(
                image, screen_size, use_lanczos, sharpen
            )
        if mode == DisplayMode.SHRINK:
            return AsyncImageProcessor._process_shrink_qimage(
                image, screen_size, use_lanczos, sharpen
            )

        logger.error(f"Unknown display mode: {mode}, defaulting to FILL (QImage)")
        return AsyncImageProcessor._process_fill_qimage(
            image, screen_size, use_lanczos, sharpen
        )

    @staticmethod
    def process_qimage_async(
        thread_manager: ThreadManager,
        image: QImage,
        screen_size: QSize,
        mode: DisplayMode = DisplayMode.FILL,
        use_lanczos: bool = False,
        sharpen: bool = False,
        *,
        callback: Optional[Callable[[TaskResult], None]] = None,
    ) -> str:
        """Submit QImage processing work to the COMPUTE pool.

        The task function runs entirely on QImage/QPainter and is safe to call on
        worker threads. Callers must perform any promotion to QPixmap or GL
        textures on the UI thread using ThreadManager.run_on_ui_thread.
        """

        if thread_manager is None:
            raise ValueError("thread_manager is required for async QImage processing")

        def _do_process() -> QImage:
            return AsyncImageProcessor.process_qimage(
                image, screen_size, mode, use_lanczos, sharpen
            )

        return thread_manager.submit_compute_task(_do_process, callback=callback)

    # ------------------------------------------------------------------
    # Internal helpers (QImage-based equivalents of ImageProcessor paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _scale_image(
        image: QImage,
        width: int,
        height: int,
        use_lanczos: bool = False,
        sharpen: bool = False,
    ) -> QImage:
        """Scale a QImage using PIL Lanczos (if available) or Qt."""

        if not PILLOW_AVAILABLE or not use_lanczos:
            return image.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        try:
            qimage = image
            if qimage.hasAlphaChannel():
                qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
                mode = "RGBA"
            else:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
                mode = "RGB"

            ptr = qimage.constBits()
            if hasattr(ptr, "setsize"):
                ptr.setsize(qimage.sizeInBytes())
                img_data = bytes(ptr)
            else:
                img_data = ptr.tobytes()

            pil_image = Image.frombytes(
                mode,
                (qimage.width(), qimage.height()),
                img_data,
            )

            # Calculate target size preserving aspect ratio (matching Qt's KeepAspectRatio)
            # This is critical for video frames which may have non-square pixels
            src_w, src_h = pil_image.size
            if src_w == 0 or src_h == 0:
                scaled_pil = pil_image
            else:
                src_ratio = src_w / src_h
                target_ratio = width / height if height > 0 else src_ratio
                
                if src_ratio > target_ratio:
                    # Source is wider - fit to width
                    new_w = width
                    new_h = int(width / src_ratio)
                else:
                    # Source is taller - fit to height
                    new_h = height
                    new_w = int(height * src_ratio)
                
                # Ensure we don't exceed requested dimensions
                new_w = min(new_w, width)
                new_h = min(new_h, height)
                
                scaled_pil = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

            if sharpen and (width < qimage.width() or height < qimage.height()):
                scale_factor = min(width / qimage.width(), height / qimage.height())
                if scale_factor < 0.5:
                    scaled_pil = scaled_pil.filter(
                        ImageFilter.UnsharpMask(
                            radius=2,
                            percent=150,
                            threshold=3,
                        )
                    )
                else:
                    scaled_pil = scaled_pil.filter(ImageFilter.SHARPEN)

            if scaled_pil.mode == "RGBA":
                data = scaled_pil.tobytes("raw", "RGBA")
                qimg = QImage(
                    data,
                    scaled_pil.width,
                    scaled_pil.height,
                    scaled_pil.width * 4,
                    QImage.Format.Format_RGBA8888,
                )
                qimg = qimg.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            else:
                data = scaled_pil.tobytes("raw", "RGB")
                qimg = QImage(
                    data,
                    scaled_pil.width,
                    scaled_pil.height,
                    scaled_pil.width * 3,
                    QImage.Format.Format_RGB888,
                )

            logger.debug(
                "Scaled QImage with Lanczos: %sx%s → %sx%s",
                qimage.width(),
                qimage.height(),
                width,
                height,
            )
            return qimg
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Lanczos scaling for QImage failed, falling back to Qt: %s", exc
            )
            return image.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    @staticmethod
    def _process_fill_qimage(
        image: QImage,
        screen_size: QSize,
        use_lanczos: bool = True,
        sharpen: bool = False,
    ) -> QImage:
        img_size = image.size()

        if screen_size.height() == 0 or img_size.height() == 0:
            logger.error(
                "Invalid dimensions (QImage FILL): screen=%sx%s, img=%sx%s",
                screen_size.width(),
                screen_size.height(),
                img_size.width(),
                img_size.height(),
            )
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)
            return result

        screen_ratio = screen_size.width() / screen_size.height()
        img_ratio = img_size.width() / img_size.height()

        if img_ratio > screen_ratio:
            scale_height = screen_size.height()
            scale_width = int(scale_height * img_ratio)
        else:
            scale_width = screen_size.width()
            scale_height = int(scale_width / img_ratio)

        scale_width = max(scale_width, screen_size.width())
        scale_height = max(scale_height, screen_size.height())

        if scale_width == img_size.width() and scale_height == img_size.height():
            scaled = image
            logger.debug(
                "Fill(QImage): Exact size match %sx%s, no scaling",
                img_size.width(),
                img_size.height(),
            )
        else:
            scaled = AsyncImageProcessor._scale_image(
                image,
                scale_width,
                scale_height,
                use_lanczos,
                sharpen,
            )
            logger.debug(
                "Fill(QImage): Scaled %sx%s → %sx%s (Lanczos=%s)",
                img_size.width(),
                img_size.height(),
                scale_width,
                scale_height,
                use_lanczos,
            )

        if scaled.width() > screen_size.width() or scaled.height() > screen_size.height():
            x_offset = (scaled.width() - screen_size.width()) // 2
            y_offset = (scaled.height() - screen_size.height()) // 2

            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)

            painter = QImagePainter(result)
            painter.drawImage(
                0,
                0,
                scaled,
                x_offset,
                y_offset,
                screen_size.width(),
                screen_size.height(),
            )
            painter.end()

            logger.info(
                "FILL(QImage): Image %sx%s → scaled %sx%s → cropped to %sx%s",
                img_size.width(),
                img_size.height(),
                scaled.width(),
                scaled.height(),
                screen_size.width(),
                screen_size.height(),
            )
            return result

        logger.info(
            "FILL(QImage): Image %sx%s → %sx%s (perfect fit)",
            img_size.width(),
            img_size.height(),
            scaled.width(),
            scaled.height(),
        )
        return scaled

    @staticmethod
    def _process_fit_qimage(
        image: QImage,
        screen_size: QSize,
        use_lanczos: bool = True,
        sharpen: bool = False,
    ) -> QImage:
        if image.height() == 0 or screen_size.height() == 0:
            logger.error(
                "Invalid dimensions for fit (QImage): screen=%sx%s, img=%sx%s",
                screen_size.width(),
                screen_size.height(),
                image.width(),
                image.height(),
            )
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)
            return result

        img_ratio = image.width() / image.height()
        screen_ratio = screen_size.width() / screen_size.height()

        if img_ratio > screen_ratio:
            target_width = screen_size.width()
            target_height = int(target_width / img_ratio)
        else:
            target_height = screen_size.height()
            target_width = int(target_height * img_ratio)

        actual_ratio = target_width / target_height
        if abs(actual_ratio - img_ratio) > 0.01:
            if img_ratio > screen_ratio:
                target_height = int(target_width / img_ratio)
            else:
                target_width = int(target_height * img_ratio)

        scaled = AsyncImageProcessor._scale_image(
            image,
            target_width,
            target_height,
            use_lanczos,
            sharpen,
        )

        result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.black)

        x_offset = (screen_size.width() - scaled.width()) // 2
        y_offset = (screen_size.height() - scaled.height()) // 2

        painter = QImagePainter(result)
        painter.drawImage(x_offset, y_offset, scaled)
        painter.end()

        logger.debug(
            "FIT(QImage): Scaled to %sx%s, centered at (%s,%s)",
            scaled.width(),
            scaled.height(),
            x_offset,
            y_offset,
        )
        return result

    @staticmethod
    def _process_shrink_qimage(
        image: QImage,
        screen_size: QSize,
        use_lanczos: bool = True,
        sharpen: bool = False,
    ) -> QImage:
        img_size = image.size()

        if img_size.height() == 0 or screen_size.height() == 0:
            logger.error(
                "Invalid dimensions for shrink (QImage): screen=%sx%s, img=%sx%s",
                screen_size.width(),
                screen_size.height(),
                img_size.width(),
                img_size.height(),
            )
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)
            return result

        if img_size.width() <= screen_size.width() and img_size.height() <= screen_size.height():
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)

            x_offset = (screen_size.width() - img_size.width()) // 2
            y_offset = (screen_size.height() - img_size.height()) // 2

            painter = QImagePainter(result)
            painter.drawImage(x_offset, y_offset, image)
            painter.end()

            logger.debug(
                "SHRINK(QImage): Original size %sx%s, centered at (%s,%s)",
                img_size.width(),
                img_size.height(),
                x_offset,
                y_offset,
            )
            return result

        img_ratio = img_size.width() / img_size.height()
        screen_ratio = screen_size.width() / screen_size.height()

        if img_ratio > screen_ratio:
            target_width = screen_size.width()
            target_height = int(target_width / img_ratio)
        else:
            target_height = screen_size.height()
            target_width = int(target_height * img_ratio)

        scaled = AsyncImageProcessor._scale_image(
            image,
            target_width,
            target_height,
            use_lanczos,
            sharpen,
        )

        result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.black)

        x_offset = (screen_size.width() - scaled.width()) // 2
        y_offset = (screen_size.height() - scaled.height()) // 2

        painter = QImagePainter(result)
        painter.drawImage(x_offset, y_offset, scaled)
        painter.end()

        logger.debug(
            "SHRINK(QImage): Scaled down to %sx%s, centered at (%s,%s)",
            scaled.width(),
            scaled.height(),
            x_offset,
            y_offset,
        )
        return result


class QImagePainter:
    """Small wrapper around QPainter for QImage targets.

    This exists only to keep imports local to this module without changing the
    public API surface.
    """

    def __init__(self, target: QImage) -> None:
        from PySide6.QtGui import QPainter  # Local import to avoid unused top-level

        self._painter = QPainter(target)

    def __getattr__(self, name):  # pragma: no cover - simple proxy
        return getattr(self._painter, name)

    def end(self) -> None:
        self._painter.end()
