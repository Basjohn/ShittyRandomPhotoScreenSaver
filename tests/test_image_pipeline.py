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
    _process_display_image_candidate,
    _process_display_with_replacements,
    _process_previous_images_with_exact_reuse,
    _process_same_image_with_replacements,
    load_and_display_image_async,
    load_and_display_image_async_with_metas,
    notify_transition_complete,
    schedule_prefetch,
)
from rendering.display_modes import DisplayMode


class _FakeScheduler:
    def __init__(self):
        self.callbacks = []

    def single_shot(self, delay, fn):
        self.callbacks.append((delay, fn))


def _solid_qimage(width: int, height: int, color: QColor) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def test_rejected_display_candidate_uses_bounded_queue_replacement(monkeypatch):
    bad = SimpleNamespace(local_path=r"C:\wall\decompression-bomb.jpg", url=None)
    good = SimpleNamespace(local_path=r"C:\wall\replacement.jpg", url=None)
    queued = [bad, good]
    engine = SimpleNamespace(
        image_queue=SimpleNamespace(next=lambda: queued.pop(0) if queued else None)
    )
    attempted = []

    def _process(_engine, _display, display_index, meta, _lanczos, _sharpen):
        attempted.append((display_index, str(meta.local_path)))
        if meta is bad:
            return None
        return {"path": str(meta.local_path)}

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    result, selected = _process_display_with_replacements(
        engine,
        object(),
        1,
        bad,
        False,
        False,
        max_replacements=2,
    )

    assert result == {"path": str(good.local_path)}
    assert selected is good
    assert attempted == [
        (1, str(bad.local_path)),
        (1, str(good.local_path)),
    ]


def test_same_image_replacement_stays_atomic_across_displays(monkeypatch):
    bad = SimpleNamespace(local_path=r"C:\wall\target-size-rejected.jpg", url=None)
    good = SimpleNamespace(local_path=r"C:\wall\common-replacement.jpg", url=None)
    queued = [good]
    engine = SimpleNamespace(
        image_queue=SimpleNamespace(next=lambda: queued.pop(0) if queued else None)
    )
    attempted = []

    def _process(_engine, _display, display_index, meta, _lanczos, _sharpen):
        attempted.append((display_index, str(meta.local_path)))
        if meta is bad and display_index == 1:
            return None
        return {"path": str(meta.local_path), "display": display_index}

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    processed, selected = _process_same_image_with_replacements(
        engine,
        [object(), object()],
        bad,
        False,
        False,
        max_replacements=1,
    )

    assert selected is good
    assert [processed[index]["path"] for index in (0, 1)] == [
        str(good.local_path),
        str(good.local_path),
    ]
    assert attempted == [
        (0, str(bad.local_path)),
        (1, str(bad.local_path)),
        (0, str(good.local_path)),
        (1, str(good.local_path)),
    ]


def test_same_image_reuses_identical_transform_processing(monkeypatch):
    meta = SimpleNamespace(local_path=r"C:\wall\shared.jpg", url=None)
    engine = SimpleNamespace(image_queue=SimpleNamespace(next=lambda: None))
    targets = [
        SimpleNamespace(
            get_target_size=lambda: QSize(2560, 1440),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
        SimpleNamespace(
            get_target_size=lambda: QSize(2560, 1440),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
    ]
    calls = []
    shared_result = {"path": str(meta.local_path)}

    def _process(_engine, _display, display_index, _meta, _lanczos, _sharpen):
        calls.append(display_index)
        return shared_result

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    processed, selected = _process_same_image_with_replacements(
        engine,
        targets,
        meta,
        False,
        False,
    )

    assert selected is meta
    assert calls == [0]
    assert processed[0] is processed[1]


def test_same_image_does_not_reuse_different_dpr_processing(monkeypatch):
    meta = SimpleNamespace(local_path=r"C:\wall\shared.jpg", url=None)
    engine = SimpleNamespace(image_queue=SimpleNamespace(next=lambda: None))
    targets = [
        SimpleNamespace(
            get_target_size=lambda: QSize(1920, 1080),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
        SimpleNamespace(
            get_target_size=lambda: QSize(1920, 1080),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=2.0,
        ),
    ]
    calls = []

    def _process(_engine, _display, display_index, _meta, _lanczos, _sharpen):
        calls.append(display_index)
        return {"path": str(meta.local_path), "display": display_index}

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    processed, selected = _process_same_image_with_replacements(
        engine,
        targets,
        meta,
        False,
        False,
    )

    assert selected is meta
    assert calls == [0, 1]
    assert processed[0] is not processed[1]


def test_previous_image_reuses_exact_source_transform_processing(monkeypatch):
    shared = SimpleNamespace(local_path=r"C:\wall\shared-previous.jpg", url=None)
    targets = [
        SimpleNamespace(
            get_target_size=lambda: QSize(2560, 1440),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
        SimpleNamespace(
            get_target_size=lambda: QSize(2560, 1440),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
    ]
    calls = []
    shared_result = {"path": str(shared.local_path)}

    def _process(_engine, _display, display_index, _meta, _lanczos, _sharpen):
        calls.append(display_index)
        return shared_result

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    processed = _process_previous_images_with_exact_reuse(
        SimpleNamespace(),
        targets,
        [shared, shared],
        True,
        False,
    )

    assert calls == [0]
    assert processed[0] is processed[1]


def test_previous_image_keeps_different_source_or_dpr_processing_separate(monkeypatch):
    first = SimpleNamespace(local_path=r"C:\wall\first-previous.jpg", url=None)
    second = SimpleNamespace(local_path=r"C:\wall\second-previous.jpg", url=None)
    targets = [
        SimpleNamespace(
            get_target_size=lambda: QSize(1920, 1080),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=1.0,
        ),
        SimpleNamespace(
            get_target_size=lambda: QSize(1920, 1080),
            display_mode=DisplayMode.FILL,
            device_pixel_ratio=2.0,
        ),
    ]
    calls = []

    def _process(_engine, _display, display_index, meta, _lanczos, _sharpen):
        calls.append((display_index, str(meta.local_path)))
        return {"path": str(meta.local_path), "display": display_index}

    monkeypatch.setattr("engine.image_pipeline._process_display_image_candidate", _process)

    different_dpr = _process_previous_images_with_exact_reuse(
        SimpleNamespace(),
        targets,
        [first, first],
        False,
        False,
    )
    different_sources = _process_previous_images_with_exact_reuse(
        SimpleNamespace(),
        [targets[0], targets[0]],
        [first, second],
        False,
        False,
    )

    assert different_dpr[0] is not different_dpr[1]
    assert different_sources[0] is not different_sources[1]
    assert calls == [
        (0, str(first.local_path)),
        (1, str(first.local_path)),
        (0, str(first.local_path)),
        (1, str(second.local_path)),
    ]


def test_scaled_cache_keeps_equal_pixel_targets_separate_across_dpr():
    path = r"C:\wall\same-pixels-different-dpr.jpg"
    raw = _solid_qimage(8, 8, QColor("navy"))
    store = {path: raw}
    cache = SimpleNamespace(
        get=lambda key: store.get(key),
        put=lambda key, value: store.__setitem__(key, value),
    )
    engine = SimpleNamespace(
        _image_cache=cache,
        _process_supervisor=None,
    )
    meta = SimpleNamespace(local_path=path, url=None)
    target_1x = SimpleNamespace(
        get_target_size=lambda: QSize(4, 4),
        display_mode=DisplayMode.FILL,
        device_pixel_ratio=1.0,
    )
    target_2x = SimpleNamespace(
        get_target_size=lambda: QSize(4, 4),
        display_mode=DisplayMode.FILL,
        device_pixel_ratio=2.0,
    )

    first = _process_display_image_candidate(
        engine,
        target_1x,
        0,
        meta,
        False,
        False,
    )
    second = _process_display_image_candidate(
        engine,
        target_2x,
        1,
        meta,
        False,
        False,
    )

    assert first is not None
    assert second is not None
    assert first.image is not second.image
    key_1x = _build_scaled_cache_key(
        path,
        4,
        4,
        DisplayMode.FILL,
        False,
        False,
        1.0,
    )
    key_2x = _build_scaled_cache_key(
        path,
        4,
        4,
        DisplayMode.FILL,
        False,
        False,
        2.0,
    )
    assert key_1x != key_2x
    assert store[key_1x] is first.image
    assert store[key_2x] is second.image


def test_exact_scaled_hit_does_not_probe_raw_or_rewrite_cache():
    path = r"C:\wall\display-ready.jpg"
    scaled_key = _build_scaled_cache_key(
        path,
        4,
        4,
        DisplayMode.FILL,
        False,
        False,
        1.0,
    )
    scaled = _solid_qimage(4, 4, QColor("green"))
    gets = []
    puts = []

    def _get(key):
        gets.append(key)
        return scaled if key == scaled_key else None

    engine = SimpleNamespace(
        _image_cache=SimpleNamespace(
            get=_get,
            put=lambda key, value: puts.append((key, value)),
        ),
        _process_supervisor=None,
    )
    display = SimpleNamespace(
        get_target_size=lambda: QSize(4, 4),
        display_mode=DisplayMode.FILL,
        device_pixel_ratio=1.0,
    )

    result = _process_display_image_candidate(
        engine,
        display,
        0,
        SimpleNamespace(local_path=path, url=None),
        False,
        False,
    )

    assert result is not None
    assert result.image is scaled
    assert gets == [scaled_key]
    assert puts == []
    assert engine._cache_runtime_stats["scaled_reuses_without_put"] == 1
    assert engine._cache_runtime_stats["raw_hits"] == 0
    assert engine._cache_runtime_stats["raw_misses"] == 0


def test_previous_async_reports_rejection_when_submit_and_fallback_fail(
    monkeypatch,
):
    display = SimpleNamespace(
        get_target_size=lambda: QSize(4, 4),
        display_mode=DisplayMode.FILL,
        _device_pixel_ratio=1.0,
    )
    display_manager = SimpleNamespace(displays=[display])

    class _RejectingThreads:
        def submit_compute_task(self, *_args, **_kwargs):
            raise RuntimeError("submission rejected")

    engine = SimpleNamespace(
        thread_manager=_RejectingThreads(),
        display_manager=display_manager,
        _runtime_generation=1,
        _shutting_down=False,
    )
    monkeypatch.setattr(
        "engine.image_pipeline.load_and_display_image",
        lambda *_args, **_kwargs: False,
    )

    assert load_and_display_image_async_with_metas(
        engine,
        [SimpleNamespace(local_path=r"C:\wall\previous.jpg", url=None)],
    ) is False


def test_normal_async_retry_retains_existing_image_change_owner():
    display = SimpleNamespace(
        get_target_size=lambda: QSize(4, 4),
        display_mode=DisplayMode.FILL,
        _device_pixel_ratio=1.0,
    )
    pending_calls = []
    display_manager = SimpleNamespace(
        displays=[display],
        set_transition_work_pending=lambda value: pending_calls.append(value),
    )

    class _Threads:
        def __init__(self):
            self.callbacks = []

        def submit_compute_task(self, _task, *, callback, category):
            self.callbacks.append((callback, category))

        def run_on_ui_thread(self, callback):
            callback()

    threads = _Threads()
    retry_meta = SimpleNamespace(local_path=r"C:\wall\retry.jpg", url=None)
    queued = [retry_meta]
    engine = SimpleNamespace(
        thread_manager=threads,
        display_manager=display_manager,
        settings_manager=SimpleNamespace(
            get=lambda key, default=None: (
                True if key == "display.same_image_all_monitors" else default
            )
        ),
        image_queue=SimpleNamespace(
            next=lambda: queued.pop(0) if queued else None,
        ),
        _runtime_generation=1,
        _shutting_down=False,
        _loading_in_progress=True,
    )
    initial_meta = SimpleNamespace(local_path=r"C:\wall\initial.jpg", url=None)

    assert load_and_display_image_async(engine, initial_meta) is True
    first_callback, first_category = threads.callbacks[0]
    assert first_category == "image.load_and_process"

    first_callback(SimpleNamespace(success=False, result=None))

    assert len(threads.callbacks) == 2
    assert threads.callbacks[1][1] == "image.load_and_process"
    assert engine._loading_in_progress is True
    assert pending_calls == []


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


def test_schedule_prefetch_does_not_decode_raw_for_display_ready_preview():
    ready_path = r"C:\wall\ready.jpg"
    missing_path = r"C:\wall\missing.jpg"
    previewed = [
        SimpleNamespace(local_path=ready_path, url=None),
        SimpleNamespace(local_path=missing_path, url=None),
    ]

    class _FakeQueue:
        def preview_upcoming(self, _count):
            return previewed

    ready_key = _build_scaled_cache_key(
        ready_path,
        3840,
        2160,
        DisplayMode.FILL,
        True,
        False,
    )

    class _FakeCache:
        def contains(self, key):
            return key == ready_key

    class _FakePrefetcher:
        def __init__(self):
            self.paths = []
            self.requests = []

        def prefetch_paths(self, paths):
            self.paths.extend(paths)

        def register_scaled_requests(self, requests):
            self.requests.extend(requests)
            return len(requests)

    prefetcher = _FakePrefetcher()
    display = SimpleNamespace(
        get_target_size=lambda: QSize(3840, 2160),
        display_mode=DisplayMode.FILL,
    )
    settings_manager = SimpleNamespace(
        get=lambda key, default=None: {
            "display.use_lanczos": True,
            "display.sharpen_downscale": False,
            "display.same_image_all_monitors": False,
        }.get(key, default)
    )
    engine = SimpleNamespace(
        image_queue=_FakeQueue(),
        _prefetcher=prefetcher,
        _prefetch_ahead=2,
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

    assert prefetcher.paths == [missing_path]
    assert [request["path"] for request in prefetcher.requests] == [missing_path]
    assert engine._cache_runtime_stats["raw_prefetch_paths"] == 1
    assert (
        engine._cache_runtime_stats["raw_prefetch_skipped_display_ready"]
        == 1
    )


def test_schedule_prefetch_with_all_display_ready_variants_creates_no_work():
    paths = [r"C:\wall\ready-one.jpg", r"C:\wall\ready-two.jpg"]
    previewed = [SimpleNamespace(local_path=path, url=None) for path in paths]

    class _FakeQueue:
        def preview_upcoming(self, _count):
            return previewed

    ready_keys = {
        _build_scaled_cache_key(
            path,
            1920,
            1080,
            DisplayMode.FIT,
            True,
            False,
        )
        for path in paths
    }

    class _FakeCache:
        def contains(self, key):
            return key in ready_keys

    class _FakePrefetcher:
        def __init__(self):
            self.prefetch_calls = []
            self.register_calls = []

        def prefetch_paths(self, paths):
            self.prefetch_calls.append(list(paths))

        def register_scaled_requests(self, requests):
            self.register_calls.append(list(requests))

    prefetcher = _FakePrefetcher()
    display = SimpleNamespace(
        get_target_size=lambda: QSize(1920, 1080),
        display_mode=DisplayMode.FIT,
    )
    engine = SimpleNamespace(
        image_queue=_FakeQueue(),
        _prefetcher=prefetcher,
        _prefetch_ahead=2,
        display_manager=SimpleNamespace(
            has_running_transition=lambda: False,
            has_transition_work_pending=lambda: False,
            displays=[display],
        ),
        _image_cache=_FakeCache(),
        settings_manager=SimpleNamespace(
            get=lambda key, default=None: {
                "display.use_lanczos": True,
                "display.sharpen_downscale": False,
                "display.same_image_all_monitors": False,
            }.get(key, default)
        ),
        _cache_runtime_stats={},
    )

    schedule_prefetch(engine)

    assert prefetcher.prefetch_calls == []
    assert prefetcher.register_calls == []
    assert engine._cache_runtime_stats["raw_prefetch_paths"] == 0
    assert (
        engine._cache_runtime_stats["raw_prefetch_skipped_display_ready"]
        == 2
    )


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


def test_notify_transition_complete_tracks_resume_counts():
    scheduler = _FakeScheduler()

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
        thread_manager=scheduler,
    )

    notify_transition_complete(engine, screen_index=1)

    assert engine._cache_runtime_stats["prefetch_resume_scheduled"] == 1
    assert scheduler.callbacks and scheduler.callbacks[0][0] == 75

    scheduler.callbacks[0][1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1


def test_notify_transition_complete_rearms_resume_while_other_display_is_pending():
    scheduler = _FakeScheduler()

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
        thread_manager=scheduler,
    )

    notify_transition_complete(engine, screen_index=0)

    assert engine._prefetch_resume_scheduled is True
    assert scheduler.callbacks and scheduler.callbacks[0][0] == 75

    scheduler.callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is True
    assert engine._cache_runtime_stats.get("prefetch_resume_runs", 0) == 0
    assert scheduler.callbacks and scheduler.callbacks[0][0] == 75

    pending_state["pending"] = False
    scheduler.callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1


def test_notify_transition_complete_rearms_until_prefetcher_cooldown_expires(monkeypatch):
    scheduler = _FakeScheduler()

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
        thread_manager=scheduler,
    )

    monkeypatch.setattr("engine.image_pipeline.schedule_prefetch", lambda eng: schedule_calls.append(eng))

    notify_transition_complete(engine, screen_index=0)

    assert engine._prefetch_resume_scheduled is True
    assert scheduler.callbacks and scheduler.callbacks[0][0] == 75

    scheduler.callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is True
    assert engine._cache_runtime_stats.get("prefetch_resume_runs", 0) == 0
    assert scheduler.callbacks and scheduler.callbacks[0][0] == 25
    assert schedule_calls == []

    cooldown_state["active"] = False
    scheduler.callbacks.pop(0)[1]()

    assert engine._prefetch_resume_scheduled is False
    assert engine._cache_runtime_stats["prefetch_resume_runs"] == 1
    assert schedule_calls == [engine]


def test_image_pipeline_does_not_use_direct_qtimer_single_shot():
    import inspect
    import engine.image_pipeline as image_pipeline

    assert "QTimer.singleShot" not in inspect.getsource(image_pipeline)
