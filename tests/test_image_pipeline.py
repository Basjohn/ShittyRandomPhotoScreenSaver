from __future__ import annotations

import logging
from types import SimpleNamespace

from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtCore import QSize

from engine.image_pipeline import (
    _build_scaled_cache_key,
    _cache_trace,
    _describe_prefetcher_state,
    _get_cached_pixmap_variants,
    notify_transition_complete,
    schedule_prefetch,
)
from rendering.display_modes import DisplayMode


def _solid_qimage(width: int, height: int, color: QColor) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def test_cache_trace_can_emit_loud_fallback_records(monkeypatch, caplog):
    monkeypatch.setattr("engine.image_pipeline.is_cache_logging_enabled", lambda: True)

    with caplog.at_level(logging.WARNING, logger="engine.image_pipeline"):
        _cache_trace("[FALLBACK] Worker fallback reason=%s", "scaled_miss", level=logging.WARNING)

    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert "[CACHE] [FALLBACK] Worker fallback reason=scaled_miss" in caplog.text


def test_cache_fallback_diagnostics_include_prefetcher_state():
    prefetcher = SimpleNamespace(
        snapshot_state=lambda: {
            "raw_inflight": 1,
            "raw_pending": 4,
            "scaled_inflight": 2,
            "scaled_pending": 3,
        }
    )
    engine = SimpleNamespace(_prefetcher=prefetcher)

    assert _describe_prefetcher_state(engine) == (
        "prefetch_state=raw_inflight:1,raw_pending:4,scaled_inflight:2,scaled_pending:3"
    )


def test_cached_pixmap_variants_prefer_scaled_variant(qt_app):
    raw_key = r"C:\wall\one.jpg"
    scaled_key = _build_scaled_cache_key(raw_key, 2560, 1440, DisplayMode.FILL, True, False)
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
    processed, original = _get_cached_pixmap_variants(
        engine,
        raw_key,
        2560,
        1440,
        DisplayMode.FILL,
        True,
        False,
    )

    assert isinstance(processed, QPixmap)
    assert not processed.isNull()
    assert processed.width() == 2560
    assert processed.height() == 1440
    assert isinstance(original, QPixmap)
    assert not original.isNull()
    assert original.width() == 3840
    assert original.height() == 2160
    assert isinstance(store[scaled_key], QPixmap)
    assert isinstance(store[raw_key], QImage)


def test_cached_pixmap_variants_fall_back_to_processed_when_raw_missing(qt_app):
    raw_key = r"C:\wall\two.jpg"
    scaled_key = _build_scaled_cache_key(raw_key, 1707, 959, DisplayMode.FILL, True, False)
    cache = SimpleNamespace()
    store = {
        scaled_key: QPixmap.fromImage(_solid_qimage(1707, 959, QColor("green"))),
    }

    cache.get = lambda key: store.get(key)
    cache.put = lambda key, value: store.__setitem__(key, value)

    engine = SimpleNamespace(_image_cache=cache)
    processed, original = _get_cached_pixmap_variants(
        engine,
        raw_key,
        1707,
        959,
        DisplayMode.FILL,
        True,
        False,
    )

    assert isinstance(processed, QPixmap)
    assert not processed.isNull()
    assert isinstance(original, QPixmap)
    assert original.cacheKey() == processed.cacheKey()


def test_schedule_prefetch_uses_preview_upcoming_and_registers_scaled_requests():
    path_a = r"C:\wall\one.jpg"
    path_b = r"C:\wall\two.jpg"
    previewed = [
        SimpleNamespace(local_path=path_a, url=None),
        SimpleNamespace(local_path=path_b, url=None),
    ]

    class _FakeQueue:
        def preview_upcoming(self, count):
            assert count == 4
            return previewed

    class _FakeCache:
        def contains(self, key):
            return False

    class _FakePrefetcher:
        def __init__(self):
            self.paths = None
            self.requests = None

        def prefetch_paths(self, paths):
            self.paths = list(paths)

        def register_scaled_requests(self, requests):
            self.requests = list(requests)

    fake_prefetcher = _FakePrefetcher()
    display = SimpleNamespace(
        get_target_size=lambda: QSize(3840, 2160),
        display_mode=DisplayMode.FIT,
    )
    settings_manager = SimpleNamespace(
        get=lambda key, default=None: {
            "display.use_lanczos": True,
            "display.sharpen_downscale": False,
        }.get(key, default)
    )
    engine = SimpleNamespace(
        image_queue=_FakeQueue(),
        _prefetcher=fake_prefetcher,
        _prefetch_ahead=4,
        display_manager=SimpleNamespace(
            has_running_transition=lambda: False,
            has_transition_work_pending=lambda: False,
            displays=[display],
        ),
        _image_cache=_FakeCache(),
        settings_manager=settings_manager,
        _cache_runtime_stats={},
    )

    schedule_prefetch(engine)

    assert fake_prefetcher.paths == [path_a, path_b]
    assert fake_prefetcher.requests is not None
    assert len(fake_prefetcher.requests) == 2
    assert {
        req["cache_key"] for req in fake_prefetcher.requests
    } == {
        _build_scaled_cache_key(path_a, 3840, 2160, DisplayMode.FIT, True, False),
        _build_scaled_cache_key(path_b, 3840, 2160, DisplayMode.FIT, True, False),
    }
    assert engine._cache_runtime_stats["scaled_prefetch_requests"] == 2


def test_schedule_prefetch_different_images_aligns_requests_to_display_order():
    paths = [
        r"C:\wall\one.jpg",
        r"C:\wall\two.jpg",
        r"C:\wall\three.jpg",
        r"C:\wall\four.jpg",
    ]
    previewed = [SimpleNamespace(local_path=path, url=None) for path in paths]

    class _FakeQueue:
        def preview_upcoming(self, count):
            return previewed

    class _FakeCache:
        def contains(self, key):
            return False

    class _FakePrefetcher:
        def __init__(self):
            self.requests = None

        def prefetch_paths(self, paths):
            self.paths = list(paths)

        def register_scaled_requests(self, requests):
            self.requests = list(requests)

    display_a = SimpleNamespace(get_target_size=lambda: QSize(1920, 1080), display_mode=DisplayMode.FILL)
    display_b = SimpleNamespace(get_target_size=lambda: QSize(1280, 720), display_mode=DisplayMode.FIT)
    settings_manager = SimpleNamespace(
        get=lambda key, default=None: {
            "display.use_lanczos": True,
            "display.sharpen_downscale": False,
            "display.same_image_all_monitors": False,
        }.get(key, default)
    )
    fake_prefetcher = _FakePrefetcher()
    engine = SimpleNamespace(
        image_queue=_FakeQueue(),
        _prefetcher=fake_prefetcher,
        _prefetch_ahead=4,
        display_manager=SimpleNamespace(
            has_running_transition=lambda: False,
            has_transition_work_pending=lambda: False,
            displays=[display_a, display_b],
        ),
        _image_cache=_FakeCache(),
        settings_manager=settings_manager,
        _cache_runtime_stats={},
    )

    schedule_prefetch(engine)

    assert fake_prefetcher.requests is not None
    assert len(fake_prefetcher.requests) == 4
    assert [request["cache_key"] for request in fake_prefetcher.requests] == [
        _build_scaled_cache_key(paths[0], 1920, 1080, DisplayMode.FILL, True, False),
        _build_scaled_cache_key(paths[1], 1280, 720, DisplayMode.FIT, True, False),
        _build_scaled_cache_key(paths[2], 1920, 1080, DisplayMode.FILL, True, False),
        _build_scaled_cache_key(paths[3], 1280, 720, DisplayMode.FIT, True, False),
    ]
    assert engine._cache_runtime_stats["scaled_prefetch_requests"] == 4


def test_schedule_prefetch_same_image_prioritizes_first_preview_for_all_display_sizes():
    paths = [
        r"C:\wall\one.jpg",
        r"C:\wall\two.jpg",
        r"C:\wall\three.jpg",
    ]
    previewed = [SimpleNamespace(local_path=path, url=None) for path in paths]

    class _FakeQueue:
        def preview_upcoming(self, count):
            return previewed

    class _FakeCache:
        def contains(self, key):
            return False

    class _FakePrefetcher:
        def __init__(self):
            self.requests = None

        def prefetch_paths(self, paths):
            self.paths = list(paths)

        def register_scaled_requests(self, requests):
            self.requests = list(requests)

    display_a = SimpleNamespace(get_target_size=lambda: QSize(1920, 1080), display_mode=DisplayMode.FILL)
    display_b = SimpleNamespace(get_target_size=lambda: QSize(1280, 720), display_mode=DisplayMode.FIT)
    settings_manager = SimpleNamespace(
        get=lambda key, default=None: {
            "display.use_lanczos": True,
            "display.sharpen_downscale": False,
            "display.same_image_all_monitors": True,
        }.get(key, default)
    )
    fake_prefetcher = _FakePrefetcher()
    engine = SimpleNamespace(
        image_queue=_FakeQueue(),
        _prefetcher=fake_prefetcher,
        _prefetch_ahead=3,
        display_manager=SimpleNamespace(
            has_running_transition=lambda: False,
            has_transition_work_pending=lambda: False,
            displays=[display_a, display_b],
        ),
        _image_cache=_FakeCache(),
        settings_manager=settings_manager,
        _cache_runtime_stats={},
    )

    schedule_prefetch(engine)

    assert fake_prefetcher.requests is not None
    assert [request["cache_key"] for request in fake_prefetcher.requests] == [
        _build_scaled_cache_key(paths[0], 1920, 1080, DisplayMode.FILL, True, False),
        _build_scaled_cache_key(paths[0], 1280, 720, DisplayMode.FIT, True, False),
        _build_scaled_cache_key(paths[1], 1920, 1080, DisplayMode.FILL, True, False),
        _build_scaled_cache_key(paths[2], 1920, 1080, DisplayMode.FILL, True, False),
    ]
    assert engine._cache_runtime_stats["scaled_prefetch_requests"] == 4


def test_notify_transition_complete_tracks_resume_counts(monkeypatch):
    callbacks = []
    monkeypatch.setattr("engine.image_pipeline.QTimer.singleShot", lambda delay, fn: callbacks.append((delay, fn)))

    class _FakePrefetcher:
        def notify_transition_complete(self):
            self.notified = True

        def get_post_transition_delay_ms(self):
            return 75

    engine = SimpleNamespace(
        _prefetcher=_FakePrefetcher(),
        _prefetch_resume_scheduled=False,
        _cache_runtime_stats={},
        image_queue=None,
    )

    notify_transition_complete(engine, screen_index=1)

    assert engine._cache_runtime_stats["prefetch_resume_scheduled"] == 1
    assert callbacks and callbacks[0][0] == 75

    callbacks[0][1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1


def test_notify_transition_complete_rearms_resume_while_other_display_is_pending(monkeypatch):
    callbacks = []
    monkeypatch.setattr("engine.image_pipeline.QTimer.singleShot", lambda delay, fn: callbacks.append((delay, fn)))

    pending_state = {"pending": True}

    class _FakeDisplayManager:
        def has_running_transition(self):
            return False

        def has_transition_work_pending(self):
            return pending_state["pending"]

    class _FakePrefetcher:
        def notify_transition_complete(self):
            self.notified = True

        def get_post_transition_delay_ms(self):
            return 75

    engine = SimpleNamespace(
        _prefetcher=_FakePrefetcher(),
        _prefetch_resume_scheduled=False,
        _cache_runtime_stats={},
        image_queue=None,
        display_manager=_FakeDisplayManager(),
    )

    notify_transition_complete(engine, screen_index=0)

    assert engine._prefetch_resume_scheduled is True
    assert callbacks and callbacks[0][0] == 75

    callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is True
    assert engine._cache_runtime_stats.get("prefetch_resume_runs", 0) == 0
    assert callbacks and callbacks[0][0] == 75

    pending_state["pending"] = False
    callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1


def test_notify_transition_complete_rearms_until_prefetcher_cooldown_expires(monkeypatch):
    callbacks = []
    monkeypatch.setattr("engine.image_pipeline.QTimer.singleShot", lambda delay, fn: callbacks.append((delay, fn)))

    cooldown_state = {"remaining": 17, "active": True}
    schedule_calls = []

    class _FakeDisplayManager:
        def has_running_transition(self):
            return False

        def has_transition_work_pending(self):
            return False

    class _FakePrefetcher:
        def notify_transition_complete(self):
            self.notified = True

        def get_post_transition_delay_ms(self):
            return 75

        def is_in_post_transition_delay(self):
            return cooldown_state["active"]

        def get_remaining_post_transition_delay_ms(self):
            return cooldown_state["remaining"]

    engine = SimpleNamespace(
        _prefetcher=_FakePrefetcher(),
        _prefetch_resume_scheduled=False,
        _cache_runtime_stats={},
        image_queue=None,
        display_manager=_FakeDisplayManager(),
    )

    monkeypatch.setattr("engine.image_pipeline.schedule_prefetch", lambda eng: schedule_calls.append(eng))

    notify_transition_complete(engine, screen_index=0)

    assert engine._prefetch_resume_scheduled is True
    assert callbacks and callbacks[0][0] == 75

    callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is True
    assert engine._cache_runtime_stats.get("prefetch_resume_runs", 0) == 0
    assert callbacks and callbacks[0][0] == 25
    assert schedule_calls == []

    cooldown_state["active"] = False
    callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1
    assert schedule_calls == [engine]
