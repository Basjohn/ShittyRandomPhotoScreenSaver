from __future__ import annotations

from types import SimpleNamespace

import pytest
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
        self.removed = []

    def get(self, key):
        return self.store.get(key)

    def put(self, key, value):
        self.store[key] = value

    def contains(self, key):
        return key in self.store

    def remove(self, key):
        if key not in self.store:
            return False
        self.removed.append(key)
        self.store.pop(key)
        return True


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


def _scaled_request(path: str, cache_key: str, *, width: int = 16, height: int = 9):
    return {
        "stats": {},
        "path": path,
        "cache_key": cache_key,
        "width": width,
        "height": height,
        "display_mode": DisplayMode.FILL,
        "use_lanczos": False,
        "sharpen": False,
    }


def _block_scaled_slots(prefetcher: ImagePrefetcher, count: int) -> None:
    prefetcher._scaled_inflight.update(f"busy-{idx}" for idx in range(count))


def _release_scaled_slots(prefetcher: ImagePrefetcher) -> None:
    prefetcher._scaled_inflight.clear()


def _submitted_scaled_keys(threads: _FakeThreads) -> list[str]:
    return [compute()[0] for compute, _callback in threads.compute_callbacks]


def test_scaled_prefetch_dispatches_later_preferred_before_earlier_ready_request(qt_app):
    general_path = r"C:\wall\general.jpg"
    preferred_path = r"C:\wall\preferred.jpg"
    cache = _FakeCache(
        {
            general_path: _solid_qimage(32, 18, "blue"),
            preferred_path: _solid_qimage(32, 18, "green"),
        }
    )
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    _block_scaled_slots(prefetcher, 2)

    assert prefetcher.register_scaled_requests(
        [
            _scaled_request(general_path, "general-scaled"),
            _scaled_request(preferred_path, "preferred-scaled"),
        ]
    ) == 2

    _release_scaled_slots(prefetcher)
    prefetcher._pump_scaled_prefetch(preferred_path=preferred_path)

    assert _submitted_scaled_keys(threads) == ["preferred-scaled", "general-scaled"]
    assert prefetcher.snapshot_budget_state()["scaled_pending"] == 0
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] == 0
    assert prefetcher._pending_scaled_keys == set()
    assert prefetcher._scaled_inflight == {"preferred-scaled", "general-scaled"}


@pytest.mark.parametrize("preferred_index", [0, 1, 2])
def test_scaled_prefetch_preserves_priority_at_every_queue_position(qt_app, preferred_index):
    paths = [fr"C:\wall\position-{idx}.jpg" for idx in range(3)]
    cache = _FakeCache(
        {path: _solid_qimage(32, 18, color) for path, color in zip(paths, ("red", "green", "blue"))}
    )
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=3)
    _block_scaled_slots(prefetcher, 3)
    requests = [
        _scaled_request(path, f"position-scaled-{idx}")
        for idx, path in enumerate(paths)
    ]
    prefetcher.register_scaled_requests(requests)

    _release_scaled_slots(prefetcher)
    prefetcher._pump_scaled_prefetch(preferred_path=paths[preferred_index])

    submitted = _submitted_scaled_keys(threads)
    assert submitted[0] == f"position-scaled-{preferred_index}"
    assert len(submitted) == len(set(submitted)) == 3
    assert set(submitted) == {f"position-scaled-{idx}" for idx in range(3)}


@pytest.mark.parametrize("available_slots", [1, 2, 4])
def test_scaled_prefetch_respects_available_slots_with_preferred_priority(qt_app, available_slots):
    paths = [fr"C:\wall\slots-{idx}.jpg" for idx in range(4)]
    cache = _FakeCache({path: _solid_qimage(32, 18, "blue") for path in paths})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=4)
    _block_scaled_slots(prefetcher, 4)
    prefetcher.register_scaled_requests(
        [_scaled_request(path, f"slots-scaled-{idx}") for idx, path in enumerate(paths)]
    )

    prefetcher._scaled_inflight = {
        f"remaining-busy-{idx}" for idx in range(4 - available_slots)
    }
    prefetcher._pump_scaled_prefetch(preferred_path=paths[-1])

    submitted = _submitted_scaled_keys(threads)
    assert submitted[0] == "slots-scaled-3"
    assert len(submitted) == len(set(submitted)) == available_slots
    budget = prefetcher.snapshot_budget_state()
    assert budget["scaled_pending"] == 4 - available_slots
    assert budget["scaled_pending_bytes"] == (4 - available_slots) * 16 * 9 * 4


def test_scaled_prefetch_keeps_not_ready_request_while_dispatching_ready_preferred(qt_app):
    waiting_path = r"C:\wall\waiting.jpg"
    preferred_path = r"C:\wall\preferred-ready.jpg"
    other_path = r"C:\wall\other-ready.jpg"
    cache = _FakeCache(
        {
            preferred_path: _solid_qimage(32, 18, "green"),
            other_path: _solid_qimage(32, 18, "blue"),
        }
    )
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    prefetcher._inflight.add(waiting_path)
    _block_scaled_slots(prefetcher, 2)
    prefetcher.register_scaled_requests(
        [
            _scaled_request(waiting_path, "waiting-scaled"),
            _scaled_request(preferred_path, "preferred-ready-scaled"),
            _scaled_request(other_path, "other-ready-scaled"),
        ]
    )

    _release_scaled_slots(prefetcher)
    prefetcher._pump_scaled_prefetch(preferred_path=preferred_path)

    assert _submitted_scaled_keys(threads) == ["preferred-ready-scaled", "other-ready-scaled"]
    assert [request["cache_key"] for request in prefetcher._pending_scaled_requests] == ["waiting-scaled"]
    assert prefetcher._pending_scaled_keys == {"waiting-scaled"}
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] == 16 * 9 * 4


def test_scaled_prefetch_rejects_stale_selected_generation_with_exact_accounting(qt_app):
    stale_path = r"C:\wall\stale-selected.jpg"
    current_path = r"C:\wall\current-selected.jpg"
    cache = _FakeCache(
        {
            stale_path: _solid_qimage(32, 18, "red"),
            current_path: _solid_qimage(32, 18, "blue"),
        }
    )
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    _block_scaled_slots(prefetcher, 2)
    prefetcher.register_scaled_requests(
        [
            _scaled_request(stale_path, "stale-selected-scaled"),
            _scaled_request(current_path, "current-selected-scaled"),
        ]
    )
    prefetcher._pending_scaled_requests[0]["_prefetch_generation"] -= 1

    _release_scaled_slots(prefetcher)
    prefetcher._pump_scaled_prefetch(preferred_path=stale_path)

    assert _submitted_scaled_keys(threads) == ["current-selected-scaled"]
    assert prefetcher.snapshot_budget_state()["scaled_pending"] == 0
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] == 0
    assert prefetcher._pending_scaled_keys == set()
    assert prefetcher._scaled_inflight == {"current-selected-scaled"}


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
    assert raw_path in cache.store
    assert cache.removed == []
    assert stats["scaled_prefetch_completed"] == 1
    assert stats.get("raw_released_after_scaled", 0) == 0


def test_scaled_prefetch_retains_raw_until_every_planned_derivative_finishes(qt_app):
    raw_path = r"C:\wall\multi-target.jpg"
    cache = _FakeCache({raw_path: _solid_qimage(640, 360, "blue")})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=2)
    stats = {}
    requests = [
        {
            "stats": stats,
            "path": raw_path,
            "cache_key": f"multi-scaled-{idx}",
            "width": width,
            "height": height,
            "display_mode": DisplayMode.FILL,
            "use_lanczos": False,
            "sharpen": False,
        }
        for idx, (width, height) in enumerate(((320, 180), (160, 90)))
    ]

    prefetcher.register_scaled_requests(requests)
    first_callback = threads.compute_callbacks[0][1]
    second_callback = threads.compute_callbacks[1][1]

    first_callback(
        SimpleNamespace(success=True, result=("multi-scaled-0", _solid_qimage(320, 180, "red")))
    )
    assert raw_path in cache.store
    assert cache.removed == []

    second_callback(
        SimpleNamespace(success=True, result=("multi-scaled-1", _solid_qimage(160, 90, "green")))
    )
    assert raw_path not in cache.store
    assert cache.removed == [raw_path]
    assert stats["raw_released_after_scaled"] == 1


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


def test_cleared_raw_prefetch_cannot_repopulate_cache_or_release_new_owner(qt_app):
    raw_path = r"C:\wall\stale-raw.jpg"
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=1)

    prefetcher.prefetch_paths([raw_path])
    stale_callback = threads.io_callbacks[0][2]

    prefetcher.clear_inflight()
    prefetcher.prefetch_paths([raw_path])
    current_callback = threads.io_callbacks[1][2]

    stale_callback(
        SimpleNamespace(
            success=True,
            result=_solid_qimage(320, 180, "red"),
        )
    )

    assert raw_path not in cache.store
    assert prefetcher.snapshot_state()["raw_inflight"] == 1

    current_image = _solid_qimage(320, 180, "blue")
    current_callback(SimpleNamespace(success=True, result=current_image))

    assert cache.store[raw_path] is current_image
    assert prefetcher.snapshot_state()["raw_inflight"] == 0


def test_cleared_scaled_prefetch_cannot_repopulate_cache_or_release_new_owner(qt_app):
    raw_path = r"C:\wall\stale-scaled.jpg"
    scaled_key = "stale-scaled-result"
    cache = _FakeCache({raw_path: _solid_qimage(640, 360, "black")})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=1)
    request = {
        "stats": {},
        "path": raw_path,
        "cache_key": scaled_key,
        "width": 320,
        "height": 180,
        "display_mode": DisplayMode.FILL,
        "use_lanczos": False,
        "sharpen": False,
    }

    prefetcher.register_scaled_requests([request])
    stale_callback = threads.compute_callbacks[0][1]

    prefetcher.clear_inflight()
    prefetcher.register_scaled_requests([request])
    current_callback = threads.compute_callbacks[1][1]

    stale_callback(
        SimpleNamespace(
            success=True,
            result=(scaled_key, _solid_qimage(320, 180, "red")),
        )
    )

    assert scaled_key not in cache.store
    assert prefetcher.snapshot_state()["scaled_inflight"] == 1

    current_image = _solid_qimage(320, 180, "blue")
    current_callback(
        SimpleNamespace(
            success=True,
            result=(scaled_key, current_image),
        )
    )

    assert cache.store[scaled_key] is current_image
    assert prefetcher.snapshot_state()["scaled_inflight"] == 0


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
    }
    assert threads.io_callbacks == []
    assert threads.compute_callbacks == []


def test_prefetch_backlogs_are_count_and_byte_bounded(qt_app):
    cache = _FakeCache()
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(
        threads,
        cache,
        max_concurrent=2,
        max_pending_requests=3,
    )
    raw_paths = [fr"C:\wall\{idx}.jpg" for idx in range(20)]

    prefetcher.prefetch_paths(raw_paths)

    state = prefetcher.snapshot_budget_state()
    assert len(threads.io_callbacks) == 2
    assert state["raw_pending"] == 3
    assert state["raw_pending"] <= state["max_pending_requests"]

    raw_path = raw_paths[0]
    cache.store[raw_path] = _solid_qimage(3840, 2160, "blue")
    prefetcher._scaled_inflight.add("busy")
    bounded = ImagePrefetcher(
        threads,
        cache,
        max_concurrent=1,
        max_pending_requests=10,
        max_pending_scaled_bytes=20 * 1024 * 1024,
    )
    bounded._scaled_inflight.add("busy")
    requests = [
        {
            "stats": {},
            "path": raw_path,
            "cache_key": f"bounded-{idx}",
            "width": 2560,
            "height": 1440,
            "display_mode": DisplayMode.FILL,
            "use_lanczos": False,
            "sharpen": False,
        }
        for idx in range(4)
    ]

    assert bounded.register_scaled_requests(requests) == 1
    budget = bounded.snapshot_budget_state()
    assert budget["scaled_pending"] == 1
    assert budget["scaled_pending_bytes"] == 2560 * 1440 * 4
    assert budget["scaled_pending_bytes"] <= budget["max_pending_scaled_bytes"]


def test_scaled_prefetch_compute_returns_qimage_not_qpixmap(qt_app):
    raw_path = r"C:\wall\worker-safe.jpg"
    cache = _FakeCache({raw_path: _solid_qimage(320, 180, "blue")})
    threads = _FakeThreads()
    prefetcher = ImagePrefetcher(threads, cache, max_concurrent=1)

    prefetcher.register_scaled_requests(
        [
            {
                "stats": {},
                "path": raw_path,
                "cache_key": "worker-safe-scaled",
                "width": 160,
                "height": 90,
                "display_mode": DisplayMode.FILL,
                "use_lanczos": False,
                "sharpen": False,
            }
        ]
    )

    compute, _callback = threads.compute_callbacks[0]
    key, image = compute()
    assert key == "worker-safe-scaled"
    assert isinstance(image, QImage)
    assert not isinstance(image, QPixmap)
