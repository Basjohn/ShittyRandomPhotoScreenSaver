from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QColor, QImage, QPixmap

from rendering.display_modes import DisplayMode
from utils.image_prefetcher import ImagePrefetcher


def _solid_qimage(width: int, height: int, color: str) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


class _FakeCache:
    def __init__(self, store=None):
        self.store = dict(store or {})

    def get(self, key):
        return self.store.get(key)

    def put(self, key, value):
        self.store[key] = value

    def contains(self, key):
        return key in self.store


class _FakeThreads:
    def __init__(self):
        self.compute_callbacks = []

    def submit_compute_task(self, func, *args, **kwargs):
        callback = kwargs.get("callback")
        self.compute_callbacks.append((func, callback))
        return "compute-task"

    def submit_task(self, *args, **kwargs):
        return "io-task"


def test_scaled_prefetch_requests_are_serialized(qt_app):
    raw_path = r"C:\wall\one.jpg"
    cache = _FakeCache({raw_path: _solid_qimage(3840, 2160, "blue")})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache)
    stats = {}

    req1 = {
        "stats": stats,
        "path": raw_path,
        "cache_key": "one-scaled",
        "width": 2560,
        "height": 1440,
        "display_mode": DisplayMode.FILL,
        "use_lanczos": False,
        "sharpen": False,
    }
    req2 = {
        "stats": stats,
        "path": raw_path,
        "cache_key": "two-scaled",
        "width": 1920,
        "height": 1080,
        "display_mode": DisplayMode.FIT,
        "use_lanczos": False,
        "sharpen": False,
    }

    prefetcher.register_scaled_requests([req1, req2])

    assert len(threads.compute_callbacks) == 1

    first_callback = threads.compute_callbacks[0][1]
    first_pixmap = QPixmap.fromImage(_solid_qimage(2560, 1440, "red"))
    first_callback(SimpleNamespace(success=True, result=("one-scaled", first_pixmap)))

    assert len(threads.compute_callbacks) == 2
    assert "one-scaled" in cache.store
    assert stats["scaled_prefetch_completed"] == 1
