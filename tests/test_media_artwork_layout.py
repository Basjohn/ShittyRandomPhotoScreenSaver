from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import QColor, QImage, QPixmap

from widgets.media.artwork_layout import compute_artwork_frame_size
from widgets.media_runtime import (
    PreparedMediaArtwork,
    compute_media_artwork_key,
    decode_media_artwork,
    prepare_media_artwork,
)
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


def test_compute_artwork_frame_size_uses_cover_frame_for_landscape_video(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(640, 360, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 200)


def test_compute_artwork_frame_size_keeps_square_art_square(qt_app) -> None:
    pixmap = QPixmap.fromImage(QImage(512, 512, QImage.Format.Format_ARGB32))

    frame = compute_artwork_frame_size(pixmap, 200)

    assert frame == QSize(200, 200)


def test_runtime_decodes_source_resolution_image_and_presenter_creates_pixmap(
    qt_app,
) -> None:
    payload = _image_bytes(640, 360)

    image = decode_media_artwork(payload)
    assert image is not None
    assert image.width() == 640
    assert image.height() == 360

    pixmap = MediaWidget._create_artwork_pixmap(image)
    assert pixmap is not None
    assert pixmap.width() == 640
    assert pixmap.height() == 360
    assert pixmap.devicePixelRatioF() == 1.0


def test_unique_artwork_key_decodes_once(monkeypatch) -> None:
    payload = b"unique-artwork"
    key = compute_media_artwork_key(payload)
    decode_calls = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)

    monkeypatch.setattr(
        "widgets.media_runtime.decode_media_artwork",
        lambda candidate: decode_calls.append(candidate) or image,
    )

    first = prepare_media_artwork(payload, key, known_key=None)
    second = prepare_media_artwork(payload, key, known_key=key)

    assert isinstance(first, PreparedMediaArtwork)
    assert first.image is image
    assert second.image is None
    assert decode_calls == [payload]


def test_unchanged_artwork_identity_skips_duplicate_decode(monkeypatch) -> None:
    payload = b"already-owned"
    key = compute_media_artwork_key(payload)
    decode_calls = []
    monkeypatch.setattr(
        "widgets.media_runtime.decode_media_artwork",
        lambda candidate: decode_calls.append(candidate),
    )

    prepared = prepare_media_artwork(payload, key, known_key=key)

    assert prepared == PreparedMediaArtwork(key=key, image=None, decode_ms=0.0)
    assert decode_calls == []


def test_widget_and_runtime_use_one_stable_artwork_identity() -> None:
    payload = b"stable-artwork-identity"

    assert MediaWidget._compute_artwork_payload_key(payload) == (
        compute_media_artwork_key(payload)
    )
