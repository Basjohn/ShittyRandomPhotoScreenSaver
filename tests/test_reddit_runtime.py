"""Focused F5 gates for presentation-neutral Reddit runtime ownership."""
from __future__ import annotations

from types import SimpleNamespace
import time

import pytest

from core.reddit_post_provider import RedditProviderResult
from core.reddit_preparation import RedditPost, write_reddit_post_cache
from widgets.reddit_runtime import RedditRuntimeConfig, RedditRuntimeService


class _Consumer:
    def __init__(self) -> None:
        self.alive = True
        self.posts = []
        self.refreshing = []
        self.errors = []

    def is_reddit_consumer_alive(self) -> bool:
        return self.alive

    def on_reddit_runtime_posts(self, posts, **metadata) -> None:
        self.posts.append((tuple(posts), dict(metadata)))

    def on_reddit_runtime_refreshing(self, refreshing: bool) -> None:
        self.refreshing.append(bool(refreshing))

    def on_reddit_runtime_error(self, error: str) -> None:
        self.errors.append(str(error))


class _ImmediateThreadManager:
    def submit_io_task(self, callback_fn, *args, callback=None, **_kwargs):
        try:
            result = callback_fn(*args)
        except Exception as exc:
            outcome = SimpleNamespace(success=False, result=None, error=str(exc))
        else:
            outcome = SimpleNamespace(success=True, result=result, error=None)
        if callback is not None:
            callback(outcome)
        return "task"


class _Provider:
    provider_id = "test"

    def __init__(self, results) -> None:
        self.results = list(results)
        self.requests = []

    def fetch_posts(self, request):
        self.requests.append(request)
        return self.results.pop(0)


@pytest.fixture(autouse=True)
def _runtime_state(monkeypatch):
    import widgets.reddit_runtime as runtime_module

    RedditRuntimeService.periodic_due_by_cache_key.clear()
    RedditRuntimeService.periodic_due_reason_by_cache_key.clear()
    RedditRuntimeService.manual_due_by_cache_key.clear()
    monkeypatch.setattr(
        runtime_module.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args: callback(*args)),
    )
    monkeypatch.setattr(
        runtime_module.ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, _callback: None),
    )


def _service(provider, *, widget_id="reddit", subreddit="python"):
    return RedditRuntimeService(
        config=RedditRuntimeConfig(
            widget_id=widget_id,
            subreddit=subreddit,
            cache_key=widget_id,
        ),
        provider=provider,
    )


def _rows(label: str):
    return [
        {
            "title": label,
            "url": f"https://example.com/{label.casefold()}",
            "score": 1,
            "created_utc": 100.0,
        }
    ]


def test_reddit_runtime_config_normalizes_member_identity_and_subreddit() -> None:
    config = RedditRuntimeConfig.from_mapping(
        {"subreddit": "https://www.reddit.com/r/Python/top", "sort": "new"},
        widget_id="reddit2",
    )
    assert config.widget_id == "reddit2"
    assert config.cache_key == "reddit2"
    assert config.subreddit == "Python"
    assert config.sort == "new"


def test_reddit_runtime_loads_startup_cache_without_provider_work(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    cached = RedditPost("Cached", "https://example.com/cached", 1, 100.0)
    assert write_reddit_post_cache(tmp_path / "reddit_posts.json", (cached,))
    provider = _Provider([])
    service = _service(provider)
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_ImmediateThreadManager())

    assert service.start() is True
    assert service.candidates == (cached,)
    assert consumer.posts == [
        (
            (cached,),
            {
                "from_cache": True,
                "source_id": None,
                "attempted_sources": (),
            },
        )
    ]
    assert provider.requests == []


def test_reddit_runtime_fetch_owns_accepted_state_and_preserves_it_on_empty(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    provider = _Provider(
        [
            RedditProviderResult.with_posts(
                _rows("Fresh"), source_id="test", attempted_sources=("test",)
            ),
            RedditProviderResult.with_posts(
                [], source_id="test", attempted_sources=("test",)
            ),
        ]
    )
    service = _service(provider)
    service._schedule_timer = lambda: None
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_ImmediateThreadManager())
    assert service.start()

    assert service.fetch()
    accepted = service.candidates
    assert accepted[0].title == "Fresh"
    assert consumer.posts[-1][1]["from_cache"] is False
    assert service.fetch()
    assert service.candidates == accepted
    assert consumer.errors == ["No Reddit posts returned"]


def test_reddit_runtime_rejects_stale_fetch_after_subreddit_change(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    held = []

    class _HeldThreadManager:
        def submit_io_task(self, callback_fn, *args, callback=None, **_kwargs):
            held.append((callback_fn, args, callback))
            return "held"

    provider = _Provider(
        [RedditProviderResult.with_posts(_rows("Stale"), source_id="test")]
    )
    service = _service(provider)
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_HeldThreadManager())
    assert service.start()
    startup_task = held.pop(0)
    assert service.fetch()
    fetch_task = held.pop(0)

    assert service.set_subreddit("learnpython") is True
    assert held  # the new subreddit owns a fresh startup generation
    prepared = fetch_task[0](*fetch_task[1])
    fetch_task[2](SimpleNamespace(success=True, result=prepared, error=None))

    assert service.candidates == ()
    assert consumer.posts == []
    assert startup_task[2] is not None


def test_reddit_runtime_manual_action_routes_once_and_reports_refreshing(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    provider = _Provider(
        [RedditProviderResult.with_posts(_rows("Manual"), source_id="test")]
    )
    service = _service(provider)
    service._schedule_timer = lambda: None
    service._manual_refresh_skip_reason = lambda: None
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_ImmediateThreadManager())
    assert service.start()

    assert service.request_refresh() is True
    assert len(provider.requests) == 1
    assert provider.requests[0].cache_key == "reddit"
    assert provider.requests[0].subreddit == "python"
    assert consumer.refreshing == [True, False]
    assert service.accepted_revision == 1


def test_reddit2_stale_startup_is_paced_without_immediate_provider_call(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    delays = []
    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: True)
    monkeypatch.setattr(
        runtime_module.ThreadManager,
        "single_shot",
        staticmethod(lambda delay, _callback: delays.append(delay)),
    )
    provider = _Provider([])
    service = _service(provider, widget_id="reddit2")
    service.attach_consumer(_Consumer())
    service.set_thread_manager(_ImmediateThreadManager())

    assert service.start() is True
    assert provider.requests == []
    assert len(delays) == 1
    assert 29_000 <= delays[0] <= 30_000
    assert (
        RedditRuntimeService.periodic_due_reason_by_cache_key["reddit2"]
        == "startup_stale_paced_due"
    )


def test_reddit_periodic_due_horizon_survives_runtime_rebuild() -> None:
    due = time.monotonic() + 45.0
    RedditRuntimeService.periodic_due_by_cache_key["reddit"] = due
    RedditRuntimeService.periodic_due_reason_by_cache_key["reddit"] = "preserved_test_due"
    first = _service(_Provider([]))
    second = _service(_Provider([]))

    first_delay, first_reason = first._refresh_due_delay_ms(0)
    second_delay, second_reason = second._refresh_due_delay_ms(0)

    assert 43_000 <= first_delay <= 45_000
    assert 43_000 <= second_delay <= first_delay
    assert first_reason == second_reason == "preserved_test_due"


def test_reddit_accepted_memory_outranks_older_startup_snapshot_on_reactivation(
    monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    old = RedditPost("Old cache", "https://example.com/old", 1, 100.0)
    assert write_reddit_post_cache(tmp_path / "reddit_posts.json", (old,))
    provider = _Provider(
        [RedditProviderResult.with_posts(_rows("Fresh memory"), source_id="test")]
    )
    service = _service(provider)
    service._schedule_timer = lambda: None
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_ImmediateThreadManager())
    assert service.start()
    assert service.fetch()
    fresh = service.candidates
    service.stop()

    assert service.start()
    assert service.candidates == fresh
    assert service.candidates[0].title == "Fresh memory"


def test_reddit_runtime_retirement_fences_work_and_clears_consumer() -> None:
    service = _service(_Provider([]))
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(_ImmediateThreadManager())
    service.retire()

    assert service.is_retired() is True
    assert service.is_running() is False
    assert service.request_refresh() is False
    with pytest.raises(RuntimeError, match="retired"):
        service.attach_consumer(consumer)


@pytest.mark.qt
def test_runtime_managed_qwidget_consumes_cache_without_local_provider_path(
    qt_app, qtbot, monkeypatch, tmp_path
) -> None:
    import widgets.reddit_runtime as runtime_module
    from widgets.reddit_widget import RedditWidget

    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    cached = RedditPost("Runtime cached", "https://example.com/runtime", 1, 100.0)
    assert write_reddit_post_cache(tmp_path / "reddit_posts.json", (cached,))
    service = _service(_Provider([]))
    widget = RedditWidget(build_default_provider=False)
    qtbot.addWidget(widget)
    widget._cache_key = "reddit"
    widget.set_subreddit("python")
    widget.set_thread_manager(_ImmediateThreadManager())
    widget.set_runtime_service(service)

    assert widget.initialize() is True
    assert widget.activate() is True
    qt_app.processEvents()

    assert widget._post_provider is None
    assert widget._runtime_service is service
    assert widget._posts == [cached]
    assert service.candidates == (cached,)
    assert widget.deactivate() is True
    assert service.is_running() is False
