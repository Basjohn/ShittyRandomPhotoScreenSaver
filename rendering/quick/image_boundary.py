"""GUI-safe capture of Qt image objects into detached Quick image state."""

from __future__ import annotations

from collections.abc import Sequence
import math

from PySide6.QtCore import QThread
from PySide6.QtGui import QGuiApplication, QImage, QPixmap

from .image_state import LogicalSize, PresentationImage


def _rgba_bytes(image: QImage) -> tuple[bytes, int]:
    width = int(image.width())
    height = int(image.height())
    packed_stride = width * 4
    source_stride = int(image.bytesPerLine())
    if source_stride < packed_stride:
        raise RuntimeError(
            f"QImage row stride {source_stride} is smaller than RGBA width {packed_stride}"
        )

    view = image.constBits()
    if hasattr(view, "tobytes"):
        source = view.tobytes()
    else:
        if hasattr(view, "setsize"):
            view.setsize(image.sizeInBytes())
        source = bytes(view)
    required = source_stride * height
    if len(source) < required:
        raise RuntimeError(
            f"QImage storage is truncated: bytes={len(source)} expected={required}"
        )
    if source_stride == packed_stride:
        return bytes(source[:required]), packed_stride
    return (
        b"".join(
            source[row * source_stride : row * source_stride + packed_stride]
            for row in range(height)
        ),
        packed_stride,
    )


def _capture_qimage(
    image: QImage,
    *,
    identity: str,
    source_path: str,
    logical_size: Sequence[float] | None,
    device_pixel_ratio: float | None,
) -> PresentationImage:
    if not isinstance(image, QImage) or image.isNull():
        raise ValueError("a non-null QImage is required")

    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = int(converted.width())
    height = int(converted.height())
    dpr = (
        float(converted.devicePixelRatio())
        if device_pixel_ratio is None
        else float(device_pixel_ratio)
    )
    if not math.isfinite(dpr) or dpr <= 0.0:
        raise ValueError("presentation image DPR must be finite and positive")
    resolved_logical_size: LogicalSize
    if logical_size is None:
        resolved_logical_size = (width / dpr, height / dpr)
    else:
        resolved_logical_size = (
            float(logical_size[0]),
            float(logical_size[1]),
        )
    rgba8, row_stride = _rgba_bytes(converted)
    return PresentationImage(
        identity=identity,
        source_path=source_path,
        logical_size=resolved_logical_size,
        device_pixel_ratio=dpr,
        pixel_size=(width, height),
        row_stride=row_stride,
        rgba8=rgba8,
    )


def capture_qimage(
    image: QImage,
    *,
    identity: str,
    source_path: str = "",
    logical_size: Sequence[float] | None = None,
    device_pixel_ratio: float | None = None,
) -> PresentationImage:
    """Synchronously deep-copy a QImage into immutable RGBA presentation state."""

    return _capture_qimage(
        image,
        identity=identity,
        source_path=source_path,
        logical_size=logical_size,
        device_pixel_ratio=device_pixel_ratio,
    )


def capture_qpixmap(
    pixmap: QPixmap,
    *,
    identity: str,
    source_path: str = "",
    logical_size: Sequence[float] | None = None,
    device_pixel_ratio: float | None = None,
) -> PresentationImage:
    """Capture a legacy pipeline QPixmap while running on Qt's GUI thread."""

    application = QGuiApplication.instance()
    if application is None:
        raise RuntimeError("QPixmap capture requires a QGuiApplication")
    if QThread.currentThread() is not application.thread():
        raise RuntimeError("QPixmap capture must run on the Qt GUI thread")
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        raise ValueError("a non-null QPixmap is required")
    resolved_dpr = (
        float(pixmap.devicePixelRatio())
        if device_pixel_ratio is None
        else float(device_pixel_ratio)
    )
    return _capture_qimage(
        pixmap.toImage(),
        identity=identity,
        source_path=source_path,
        logical_size=logical_size,
        device_pixel_ratio=resolved_dpr,
    )
