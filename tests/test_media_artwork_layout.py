from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import QColor, QImage, QPixmap

from widgets.media.artwork_layout import compute_artwork_frame_size
from widgets.media_widget import MediaWidget


def _image_bytes(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#cc5500"))
    payload = QByteArray()
    buffer = QBuffer(payload)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(payload)


def test_compute_artwork_frame_size_preserves_landscape_video_ratio(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(640, 360, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 112)


def test_compute_artwork_frame_size_keeps_square_art_square(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(512, 512, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 200)


def test_decode_artwork_pixmap_uses_reader_and_normalizes_dpr(qt_app) -> None:
    payload = _image_bytes(640, 360)

    pixmap = MediaWidget._decode_artwork_pixmap(SimpleNamespace(), payload)

    assert pixmap is not None
    assert pixmap.width() == 640
    assert pixmap.height() == 360
    assert pixmap.devicePixelRatioF() == 1.0
