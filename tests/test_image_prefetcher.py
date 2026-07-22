from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QColor, QImage

from rendering.display_modes import DisplayMode
from rendering.image_upload_payload import ImageUploadPayload
from utils.image_prefetcher import ImagePrefetcher


def _solid_qimage(width: int, height: int, color: str) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


class _FakeCache:
    def __init__(self, store=None, max_memory_bytes=0):
        self.store = dict(store or {})
        self.max_memory_bytes = max_memory_bytes

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


class _NoPositionalPopList(list):
    """Regression oracle for the production stale-index dispatch failure."""

    def pop(self, index=-1):
        raise AssertionError(f"scaled prefetch dispatch used positional pop({index})")


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
    first_image = _solid_qimage(2560, 1440, "red")
    first_callback(SimpleNamespace(success=True, result=("one-scaled", first_image)))

    assert "one-scaled" in cache.store
    assert isinstance(cache.store["one-scaled"], QImage)
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
    callback(SimpleNamespace(success=True, result=("scaled-1", _solid_qimage(2560, 1440, "red"))))

    assert len(threads.compute_callbacks) == 3


def test_scaled_prefetch_dispatch_partitions_queue_without_stale_indices(qt_app):
    preferred_path = r"C:\wall\preferred.jpg"
    other_path = r"C:\wall\other.jpg"
    cache = _FakeCache(
        {
            preferred_path: _solid_qimage(640, 360, "blue"),
            other_path: _solid_qimage(640, 360, "green"),
        }
    )
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    requests = [
        {
            "stats": {},
            "path": other_path,
            "cache_key": "other-scaled",
            "width": 320,
            "height": 180,
            "display_mode": DisplayMode.FILL,
        },
        {
            "stats": {},
            "path": preferred_path,
            "cache_key": "preferred-scaled",
            "width": 320,
            "height": 180,
            "display_mode": DisplayMode.FILL,
        },
        {
            "stats": {},
            "path": other_path,
            "cache_key": "deferred-scaled",
            "width": 160,
            "height": 90,
            "display_mode": DisplayMode.FIT,
        },
    ]

    with prefetcher._lock:
        prefetcher._pending_scaled_requests = _NoPositionalPopList(requests)
        prefetcher._pending_scaled_keys = {
            str(request["cache_key"]) for request in requests
        }

    prefetcher._pump_scaled_prefetch(preferred_path=preferred_path)

    assert len(threads.compute_callbacks) == 2
    assert prefetcher._scaled_inflight == {"preferred-scaled", "other-scaled"}
    assert [
        request["cache_key"] for request in prefetcher._pending_scaled_requests
    ] == ["deferred-scaled"]


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
        "streamed_raw": 0,
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
        "streamed_raw": 0,
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
        "streamed_raw": 0,
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
        "streamed_raw": 0,
    }
    assert threads.compute_callbacks == []


def test_prefetch_registration_survives_transition_cooldown(qt_app):
    raw_path = r"C:\wall\one.jpg"
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(
        threads,
        cache,
        post_transition_delay_ms=10_000,
    )
    prefetcher.notify_transition_complete()

    prefetcher.prefetch_paths([raw_path])
    queued = prefetcher.register_scaled_requests(
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

    assert queued == 1
    assert prefetcher.snapshot_state() == {
        "raw_inflight": 0,
        "raw_pending": 1,
        "scaled_inflight": 0,
        "scaled_pending": 1,
        "streamed_raw": 0,
    }
    assert threads.io_callbacks == []
    assert threads.compute_callbacks == []


def test_oversized_raw_prefetch_streams_to_scaler_without_entering_lru(qt_app):
    raw_path = r"C:\wall\huge.png"
    cache = _FakeCache(max_memory_bytes=8 * 1024 * 1024)
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=1)

    prefetcher.prefetch_paths([raw_path])
    queued = prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": "huge-scaled",
                "width": 640,
                "height": 360,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
        ]
    )

    assert queued == 1
    io_callback = threads.io_callbacks[0][2]
    io_callback(SimpleNamespace(success=True, result=_solid_qimage(1024, 1024, "blue")))

    assert raw_path not in cache.store
    assert len(threads.compute_callbacks) == 1
    assert prefetcher.snapshot_state()["streamed_raw"] == 1

    compute, callback = threads.compute_callbacks[0]
    payload = compute()
    assert payload is not None
    key, image = payload
    assert key == "huge-scaled"
    assert isinstance(image, ImageUploadPayload)
    assert (image.width, image.height) == (640, 360)

    callback(SimpleNamespace(success=True, result=payload))

    assert "huge-scaled" in cache.store
    assert isinstance(cache.store["huge-scaled"], ImageUploadPayload)
    assert prefetcher.snapshot_state()["streamed_raw"] == 0


def test_oversized_raw_prefetch_stays_alive_until_all_scaled_consumers_finish(qt_app):
    raw_path = r"C:\wall\huge-multi.png"
    cache = _FakeCache(max_memory_bytes=8 * 1024 * 1024)
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=1)

    prefetcher.prefetch_paths([raw_path])
    queued = prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": "huge-wide",
                "width": 640,
                "height": 360,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            },
            {
                "stats": {},
                "path": raw_path,
                "cache_key": "huge-tall",
                "width": 360,
                "height": 640,
                "display_mode": DisplayMode.FIT,
                "use_lanczos": False,
                "sharpen": False,
            },
        ]
    )

    assert queued == 2
    threads.io_callbacks[0][2](
        SimpleNamespace(success=True, result=_solid_qimage(1024, 1024, "blue"))
    )
    assert len(threads.compute_callbacks) == 1
    assert prefetcher.snapshot_state()["streamed_raw"] == 1

    first_compute, first_callback = threads.compute_callbacks[0]
    first_payload = first_compute()
    first_callback(SimpleNamespace(success=True, result=first_payload))

    assert len(threads.compute_callbacks) == 2
    assert prefetcher.snapshot_state()["streamed_raw"] == 1

    second_compute, second_callback = threads.compute_callbacks[1]
    second_payload = second_compute()
    second_callback(SimpleNamespace(success=True, result=second_payload))

    assert {"huge-wide", "huge-tall"}.issubset(cache.store)
    assert raw_path not in cache.store
    assert prefetcher.snapshot_state()["streamed_raw"] == 0
