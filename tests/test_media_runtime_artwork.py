"""Presentation-neutral Media artwork decode and identity contracts."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage

from widgets.media_runtime import (
    PreparedMediaArtwork,
    compute_media_artwork_key,
    decode_media_artwork,
    prepare_media_artwork,
)


def _image_bytes(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#cc5500"))
    payload = QByteArray()
    buffer = QBuffer(payload)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(payload)


def test_runtime_decodes_source_resolution_image() -> None:
    image = decode_media_artwork(_image_bytes(640, 360))

    assert image is not None
    assert image.size().width() == 640
    assert image.size().height() == 360


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
