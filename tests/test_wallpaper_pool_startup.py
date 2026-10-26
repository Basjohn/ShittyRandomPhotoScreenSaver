"""Cold RSS startup uses one bounded IO admission and the real foreground seam."""
from __future__ import annotations

import os
import threading
from types import SimpleNamespace

import pytest
from PIL import Image


class _Tasks:
    def __init__(self):
        self.io = []
        self.ui = []

    def submit_io_task(self, task, **kwargs):
        self.io.append(task)

    def single_shot(self, delay, task):
        assert delay == 0
        self.ui.append(task)

    def run_io(self):
        errors = []
        def run():
            try:
                self.io.pop(0)()
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=run)
        thread.start()
        thread.join(5)
        assert not thread.is_alive()
        assert not errors


@pytest.fixture
def startup(qt_app, tmp_path, monkeypatch):
    import engine.image_pipeline as pipeline
    import sources.rss.coordinator as module
    import sources.rss.image_fetch as fetch
    from core.feeds.models import FeedDocument, FeedImageCandidate, FeedItem
    from core.settings.settings_manager import SettingsManager
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from sources.rss.pools import WallpaperPoolSelection

    settings = SettingsManager(application="PoolStartup", storage_base_dir=tmp_path)
    settings.set("sources.folders", [])
    settings.set("sources.rss_feeds", [])
    engine = ScreensaverEngine()
    engine._state = EngineState.STOPPED
    engine.settings_manager = settings
    tasks = _Tasks()
    engine.thread_manager = tasks
    engine.display_manager = SimpleNamespace(
        is_selection_suspended=lambda: False, has_presented_image=lambda: False,
        has_admissible_transition_for_open_batch=lambda: True,
    )
    engine.rss_coordinator = module.RSSCoordinator(
        feed_urls=[], cache_dir=tmp_path / "rss", required_size=(2560, 1440),
        thread_manager=tasks, shutdown_check=lambda: not engine._shutting_down,
        pool_selection=WallpaperPoolSelection(True, ("nasa.space", "wallhaven.nature"), "latest"),
    )
    calls = []
    main_thread = threading.get_ident()
    def document(url, **kwargs):
        assert threading.get_ident() != main_thread
        calls.append(url)
        if "images-api.nasa.gov/search" in url:
            return FeedDocument("NASA", url, "nasa-search", (FeedItem("nasa", "NASA", "https://images-api.nasa.gov/asset/test"),))
        if "/asset/" in url:
            candidate = FeedImageCandidate("https://cdn.test/small.jpg", width=512, height=512)
        else:
            candidate = FeedImageCandidate("https://cdn.test/large.jpg", width=4000, height=3000)
        return FeedDocument("images", url, "test", (FeedItem("one", "one", url, images=(candidate,)),))
    def image(url, directory, *, file_stem, **kwargs):
        assert threading.get_ident() != main_thread
        path = directory / (file_stem + ".png")
        Image.frombytes("RGB", (16, 16), os.urandom(768)).save(path)
        return fetch.WallpaperFile(path, 4000, 3000)
    monkeypatch.setattr(engine.rss_coordinator, "_document", document)
    monkeypatch.setattr(fetch, "fetch_wallpaper", image)
    monkeypatch.setattr(module, "HOST_MIN_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(engine, "_prepare_random_transition_if_needed", lambda: None)
    monkeypatch.setattr(engine, "_try_begin_image_change_work", lambda **kwargs: True)
    monkeypatch.setattr(pipeline, "image_processing_authority_available", lambda engine: True)
    foreground = []
    def admit(metadata, **kwargs):
        assert threading.get_ident() == main_thread
        foreground.append(metadata)
        return True
    monkeypatch.setattr(engine, "_load_and_display_image_async", admit)
    yield engine, tasks, calls, foreground
    if engine.rss_coordinator is not None:
        engine.rss_coordinator.request_stop()
    engine._end_replacement_watchdog("test_cleanup")
    engine._state = EngineState.SHUTTING_DOWN
    engine.__class__._instance_running = False


def test_nasa_zero_opportunity_advances_same_io_job_and_reaches_foreground_owner(startup):
    engine, tasks, calls, foreground = startup
    assert engine._build_image_queue()
    assert calls == [] and len(tasks.io) == 1
    assert engine.image_queue.total_images() == 0
    assert engine.start()
    assert tasks.ui == []  # no GUI polling while the existing IO job is pending
    tasks.run_io()
    assert len(calls) == 3  # NASA search + small original manifest, then Wallhaven
    assert engine.image_queue.total_images() == 1
    assert foreground == [] and len(tasks.ui) == 1
    tasks.ui.pop(0)()
    assert foreground == [engine._current_image]
    assert foreground[0].url == "https://cdn.test/large.jpg"


@pytest.mark.parametrize("cancel_after_io", [False, True])
def test_shutdown_fences_startup_work_and_queued_first_image(startup, cancel_after_io):
    from engine.screensaver_engine import EngineState
    engine, tasks, calls, foreground = startup
    assert engine._build_image_queue()
    assert engine.start()
    if cancel_after_io:
        tasks.run_io()
    engine._state = EngineState.SHUTTING_DOWN
    engine.rss_coordinator.request_stop()
    if not cancel_after_io:
        tasks.run_io()
        assert calls == []
    for callback in tasks.ui:
        callback()
    assert foreground == []


def test_no_configured_source_still_fails_queue_construction(startup):
    engine, tasks, calls, foreground = startup
    engine.rss_coordinator = None
    assert not engine._build_image_queue()
    assert not tasks.io and not tasks.ui and not foreground


def test_waiting_io_pauses_same_reveal_watchdog_and_rearms_at_foreground_admission(startup, monkeypatch):
    from core.diagnostics import hang_watchdog
    engine, tasks, calls, foreground = startup
    events = []
    monkeypatch.setattr(hang_watchdog, "disarm", lambda label: events.append(("pause", label)))
    monkeypatch.setattr(hang_watchdog, "arm", lambda label, **kwargs: events.append(("arm", label)))
    engine._replacement_watchdog_label = "owned_replacement"
    assert engine._build_image_queue() and engine.start()
    assert events == [("pause", "owned_replacement")]
    tasks.run_io()
    tasks.ui.pop(0)()
    assert events[-1] == ("arm", "owned_replacement")
    assert foreground


def test_bootstrap_empty_sources_have_finite_document_budget(startup, monkeypatch):
    from sources.rss.pools import MAX_STARTUP_DOCUMENTS, WallpaperPoolRotation, WallpaperPoolSelection
    engine, tasks, calls, foreground = startup
    coordinator = engine.rss_coordinator
    urls = [f"https://custom.test/{i}" for i in range(20)]
    coordinator._pool_rotation = WallpaperPoolRotation(urls, WallpaperPoolSelection(False, (), "latest"), seed="test")
    monkeypatch.setattr(coordinator, "_document", lambda url: calls.append(url))
    assert engine._build_image_queue()
    tasks.run_io()
    assert len(calls) == MAX_STARTUP_DOCUMENTS


def test_bootstrap_deadline_and_cancellation_do_not_extend_into_another_opportunity(startup, monkeypatch):
    import sources.rss.coordinator as module
    from sources.rss.pools import STARTUP_ACQUISITION_SECONDS
    engine, tasks, calls, foreground = startup
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    def expired(url, **kwargs):
        calls.append(url)
        clock[0] += STARTUP_ACQUISITION_SECONDS + 1
    monkeypatch.setattr(engine.rss_coordinator, "_document", expired)
    assert engine._build_image_queue()
    tasks.run_io()
    assert len(calls) == 1


@pytest.mark.parametrize("invalidate", ["stop", "generation"])
def test_late_startup_completion_cannot_admit_a_retired_source_or_runtime(startup, invalidate):
    engine, tasks, calls, foreground = startup
    assert engine._build_image_queue() and engine.start()
    tasks.run_io()
    if invalidate == "stop":
        engine.rss_coordinator.request_stop()
    else:
        engine._advance_runtime_generation("test replacement")
    tasks.ui.pop(0)()
    assert foreground == []


def test_initial_source_attempt_budget_is_shared_across_empty_opportunities(startup, monkeypatch):
    import sources.rss.coordinator as module
    import sources.rss.image_fetch as fetch
    from core.feeds.models import FeedDocument, FeedItem, FeedImageCandidate
    from sources.rss.pools import WallpaperPoolRotation, WallpaperPoolSelection
    engine, tasks, calls, foreground = startup
    urls = [f"https://custom.test/{i}" for i in range(20)]
    engine.rss_coordinator._pool_rotation = WallpaperPoolRotation(urls, WallpaperPoolSelection(False, (), "latest"), seed="test")
    def document(url):
        calls.append(url)
        items = tuple(FeedItem(str(i), str(i), url, images=(FeedImageCandidate(f"https://cdn.test/{url.rsplit('/', 1)[1]}/{i}.jpg"),)) for i in range(16))
        return FeedDocument("fixture", url, "fixture", items)
    attempts = []
    def reject(url, *args, **kwargs):
        attempts.append(url)
        raise fetch.WallpaperRejected("fixture rejection")
    monkeypatch.setattr(engine.rss_coordinator, "_document", document)
    monkeypatch.setattr(fetch, "fetch_wallpaper", reject)
    assert engine._build_image_queue()
    tasks.run_io()
    assert len(attempts) == module.MAX_IMAGE_ATTEMPTS_PER_PASS


def test_existing_background_cadence_can_admit_a_configured_empty_queue(startup):
    engine, tasks, calls, foreground = startup
    schedules = []
    tasks.schedule_recurring = lambda interval, callback: schedules.append(callback) or object()
    assert engine._build_image_queue()
    engine._start_rss_background_refresh_if_needed()
    assert schedules == [engine._background_refresh_rss]
