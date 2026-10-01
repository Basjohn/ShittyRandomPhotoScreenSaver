"""Async/QImage-based image processing helpers.

QImage-first processing for the active asynchronous image pipeline. The
resolved display mode and quality choices are required inputs; this module
does not own product defaults and is safe to run off the GUI thread.
"""
from __future__ import annotations


from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage

from core.logging.logger import get_logger
from rendering.display_modes import DisplayMode
from rendering.image_quality import RESAMPLE_FILTERS, opaque_rgb, process_image


logger = get_logger(__name__)

try:
    from PIL import Image  # type: ignore[import]

    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    PILLOW_AVAILABLE = False
    logger.warning("PIL/Pillow not available; selected quality filters cannot run")


class AsyncImageProcessor:
    """QImage-first image processing utilities.

    These helpers are intended for use on the COMPUTE pool. They avoid
    ``QPixmap`` entirely so they are safe to call off the GUI thread.
    """

    @staticmethod
    def process_qimage(
        image: QImage,
        screen_size: QSize,
        mode: DisplayMode,
        resample_filter: str,
        sharpen: bool,
    ) -> QImage:
        """Process one resolved image request into the requested screen size."""

        if image.isNull():
            logger.warning("[CACHE][FALLBACK] QImage is null, returning empty ARGB32 image")
            result = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            result.fill(Qt.GlobalColor.black)
            return result

        if resample_filter not in RESAMPLE_FILTERS:
            raise ValueError(f"Unknown resolved resample filter: {resample_filter!r}")
        if resample_filter != "smooth" or sharpen:
            if not PILLOW_AVAILABLE:
                raise RuntimeError("Pillow is required for the selected image quality")
            alpha = image.hasAlphaChannel()
            converted = image.convertToFormat(
                QImage.Format.Format_RGBA8888 if alpha else QImage.Format.Format_RGB888
            )
            pixel_mode = "RGBA" if alpha else "RGB"
            pil = Image.frombytes(pixel_mode, (converted.width(), converted.height()),
                                  converted.constBits(), "raw", pixel_mode, converted.bytesPerLine(), 1)
            result = process_image(opaque_rgb(pil), (screen_size.width(), screen_size.height()),
                                   mode.value, resample_filter, sharpen)
            rgba = result.convert("RGBA")
            data = rgba.tobytes()
            # The output owns its storage independently of the Pillow intermediates.
            return QImage(data, rgba.width, rgba.height, rgba.width * 4,
                          QImage.Format.Format_RGBA8888).copy()

        if mode == DisplayMode.FILL:
            return AsyncImageProcessor._process_fill_qimage(
                image, screen_size
            )
        if mode == DisplayMode.FIT:
            return AsyncImageProcessor._process_fit_qimage(
                image, screen_size
            )
        if mode == DisplayMode.SHRINK:
            return AsyncImageProcessor._process_shrink_qimage(
                image, screen_size
            )

        raise ValueError(f"Unknown resolved display mode: {mode!r}")

    # ------------------------------------------------------------------
    # Internal helpers. Every product choice is passed from the resolved caller;
    # these helpers own only image-processing mechanics.
    # ------------------------------------------------------------------

    @staticmethod
    def _scale_image(
        image: QImage,
        width: int,
        height: int,
    ) -> QImage:
        """Scale the ordinary Smooth path without a Qt/Pillow round-trip."""
        return image.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

    @staticmethod
    def _process_fill_qimage(
        image: QImage,
        screen_size: QSize,
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

        # Round the covering extent up before the aspect-preserving scaler.
        # Rounding down can make it fit *inside* the display by one column
        # (4014x2258 -> 3839x2160 for a 3840x2160 request), breaking both FILL
        # coverage and the worker's exact packed-RGBA dimensions.
        if img_size.width() * screen_size.height() > screen_size.width() * img_size.height():
            scale_height = screen_size.height()
            scale_width = (scale_height * img_size.width() + img_size.height() - 1) // img_size.height()
        else:
            scale_width = screen_size.width()
            scale_height = (scale_width * img_size.height() + img_size.width() - 1) // img_size.width()

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
            )
            logger.debug(
                "Fill(QImage): Scaled %sx%s → %sx%s (filter=%s)",
                img_size.width(),
                img_size.height(),
                scale_width,
                scale_height,
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

        if scaled.hasAlphaChannel():
            # Wallpaper pixels are opaque (Guardrails): composite any source
            # transparency over black, exactly as the cropping/padding branches do.
            opaque = QImage(screen_size, QImage.Format.Format_ARGB32_Premultiplied)
            opaque.fill(Qt.GlobalColor.black)
            painter = QImagePainter(opaque)
            painter.drawImage(0, 0, scaled)
            painter.end()
            scaled = opaque

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
