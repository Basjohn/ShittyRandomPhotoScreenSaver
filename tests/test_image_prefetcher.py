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
        self.io_callbacks = []

    def submit_compute_task(self, func, *args, **kwargs):
        callback = kwargs.get("callback")
        self.compute_callbacks.append((func, callback))
        return "compute-task"

    def submit_task(self, *args, **kwargs):
        func = args[1] if len(args) > 1 else None
        path = args[2] if len(args) > 2 else None
        callback = kwargs.get("callback")
        self.io_callbacks.append((func, path, callback))
        return "io-task"


def test_scaled_prefetch_requests_use_bounded_parallelism(qt_app):
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

    assert len(threads.compute_callbacks) == 2

    first_callback = threads.compute_callbacks[0][1]
    first_pixmap = QPixmap.fromImage(_solid_qimage(2560, 1440, "red"))
    first_callback(SimpleNamespace(success=True, result=("one-scaled", first_pixmap)))

    assert "one-scaled" in cache.store
    assert stats["scaled_prefetch_completed"] == 1


def test_scaled_prefetch_requests_queue_beyond_parallel_limit(qt_app):
    raw_path = r"C:\wall\one.jpg"
    cache = _FakeCache({raw_path: _solid_qimage(3840, 2160, "blue")})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache)

    requests = []
    for idx, size in enumerate([(2560, 1440), (1920, 1080), (1707, 959)], start=1):
        requests.append(
            {
                "stats": {},
                "path": raw_path,
                "cache_key": f"scaled-{idx}",
                "width": size[0],
                "height": size[1],
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
        )

    prefetcher.register_scaled_requests(requests)

    assert len(threads.compute_callbacks) == 2

    callback = threads.compute_callbacks[0][1]
    callback(SimpleNamespace(success=True, result=("scaled-1", QPixmap.fromImage(_solid_qimage(2560, 1440, "red")))))

    assert len(threads.compute_callbacks) == 3


def test_scaled_prefetch_requests_refuse_paths_without_raw_producers(qt_app):
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    raw_paths = [fr"C:\wall\{idx}.jpg" for idx in range(5)]

    queued = prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": f"scaled-{idx}",
                "width": 2560,
                "height": 1440,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
            for idx, raw_path in enumerate(raw_paths)
        ]
    )

    assert queued == 0
    assert len(threads.io_callbacks) == 0
    assert prefetcher.snapshot_state() == {
        "raw_inflight": 0,
        "raw_pending": 0,
        "scaled_inflight": 0,
        "scaled_pending": 0,
    }


def test_prefetch_keeps_raw_backlog_for_full_preview_window(qt_app):
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    raw_paths = [fr"C:\wall\{idx}.jpg" for idx in range(5)]

    prefetcher.prefetch_paths(raw_paths)
    queued = prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": f"scaled-{idx}",
                "width": 2560,
                "height": 1440,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
            for idx, raw_path in enumerate(raw_paths)
        ]
    )

    assert queued == 5
    assert len(threads.io_callbacks) == 2
    assert prefetcher.snapshot_state() == {
        "raw_inflight": 2,
        "raw_pending": 3,
        "scaled_inflight": 0,
        "scaled_pending": 5,
    }

    first_callback = threads.io_callbacks[0][2]
    first_callback(SimpleNamespace(success=True, result=_solid_qimage(3840, 2160, "blue")))

    assert raw_paths[0] in cache.store
    assert len(threads.io_callbacks) == 3
    assert len(threads.compute_callbacks) == 1
    assert prefetcher.snapshot_state() == {
        "raw_inflight": 2,
        "raw_pending": 2,
        "scaled_inflight": 1,
        "scaled_pending": 4,
    }


def test_scaled_prefetch_registration_skips_during_transition_cooldown(qt_app):
    raw_path = r"C:\wall\one.jpg"
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(
        threads,
        cache,
        post_transition_delay_ms=10_000,
    )
    prefetcher.notify_transition_complete()

    prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": "one-scaled",
                "width": 2560,
                "height": 1440,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
        ]
    )

    assert prefetcher.snapshot_state() == {
        "raw_inflight": 0,
        "raw_pending": 0,
        "scaled_inflight": 0,
        "scaled_pending": 0,
    }
    assert threads.compute_callbacks == []
