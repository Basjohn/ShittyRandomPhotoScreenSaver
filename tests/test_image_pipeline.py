from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QColor, QImage, QPixmap

from engine.image_pipeline import _get_cached_pixmap_variants


def _solid_qimage(width: int, height: int, color: QColor) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def test_cached_pixmap_variants_prefer_scaled_variant(qt_app):
    scaled_key = r"C:\wall\one.jpg|scaled:2560x1440"
    raw_key = r"C:\wall\one.jpg"
    cache = SimpleNamespace()
    store = {
        scaled_key: _solid_qimage(2560, 1440, QColor("red")),
        raw_key: _solid_qimage(3840, 2160, QColor("blue")),
    }

    def _get(key):
        return store.get(key)

    def _put(key, value):
        store[key] = value

    cache.get = _get
    cache.put = _put

    engine = SimpleNamespace(_image_cache=cache)
    processed, original = _get_cached_pixmap_variants(engine, raw_key, 2560, 1440)

    assert isinstance(processed, QPixmap)
    assert not processed.isNull()
    assert processed.width() == 2560
    assert processed.height() == 1440
    assert isinstance(original, QPixmap)
    assert not original.isNull()
    assert original.width() == 3840
    assert original.height() == 2160
    assert isinstance(store[scaled_key], QPixmap)
    assert isinstance(store[raw_key], QPixmap)


def test_cached_pixmap_variants_fall_back_to_processed_when_raw_missing(qt_app):
    scaled_key = r"C:\wall\two.jpg|scaled:1707x959"
    raw_key = r"C:\wall\two.jpg"
    cache = SimpleNamespace()
    store = {
        scaled_key: QPixmap.fromImage(_solid_qimage(1707, 959, QColor("green"))),
    }

    cache.get = lambda key: store.get(key)
    cache.put = lambda key, value: store.__setitem__(key, value)

    engine = SimpleNamespace(_image_cache=cache)
    processed, original = _get_cached_pixmap_variants(engine, raw_key, 1707, 959)

    assert isinstance(processed, QPixmap)
    assert not processed.isNull()
    assert isinstance(original, QPixmap)
    assert original.cacheKey() == processed.cacheKey()
