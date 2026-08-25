"""Focused tests for the presentation-neutral Weather runtime owner."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from types import SimpleNamespace
import threading

import pytest

from widgets.weather_runtime import WeatherRuntimeService


class _QueuedIoManager:
    def __init__(self) -> None:
        self.tasks = []

    def submit_io_task(
        self,
        func,
        *args,
        callback=None,
        category="uncategorized",
        **kwargs,
    ):
        self.tasks.append(
            SimpleNamespace(
                func=func,
                args=args,
                kwargs=kwargs,
                callback=callback,
                category=category,
            )
        )
        return f"task-{len(self.tasks)}"


class _WeatherConsumer:
    """Minimal implementation of the live Weather runtime consumer protocol."""

    def __init__(self) -> None:
        self.alive = True
        self.pending_first_show = True
        self.states: list[tuple[dict, bool]] = []
        self.applied: list[dict] = []
        self.errors: list[str] = []

    def is_weather_consumer_alive(self) -> bool:
        return self.alive

    def on_weather_state(self, data, *, from_cache: bool) -> None:
        self.states.append((dict(data), bool(from_cache)))
        self.pending_first_show = False

    def apply_weather_data(self, data) -> None:
        self.applied.append(dict(data))

    def on_weather_error(self, error: str) -> None:
        self.errors.append(str(error))

    def weather_pending_first_show(self) -> bool:
        return self.pending_first_show


def _run_queued_io_task(task) -> None:
    try:
        value = task.func(*task.args, **task.kwargs)
        result = SimpleNamespace(success=True, result=value, error=None)
    except Exception as exc:  # pragma: no cover - asserted through callback state
        result = SimpleNamespace(success=False, result=None, error=exc)
    if task.callback is not None:
        task.callback(result)


def _service(
    *,
    location: str = "London",
    manager=None,
    consumer: _WeatherConsumer | None = None,
) -> tuple[WeatherRuntimeService, _WeatherConsumer]:
    owner = WeatherRuntimeService(runtime_generation=0)
    target = consumer or _WeatherConsumer()
    owner.attach_consumer(target)
    owner.set_location(location)
    if manager is not None:
        owner.set_thread_manager(manager)
    return owner, target


@pytest.fixture(autouse=True)
def isolated_weather_cache(tmp_path, monkeypatch):
    widget_cache = tmp_path / "weather_widget_cache.json"
    provider_cache = tmp_path / "open_meteo_cache.json"
    monkeypatch.setattr("widgets.weather_runtime._CACHE_FILE", widget_cache)
    monkeypatch.setattr(
        "weather.open_meteo_provider._WEATHER_CACHE_FILE",
        provider_cache,
    )


def test_weather_runtime_construction_is_filesystem_and_provider_inert(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.load_weather_startup_snapshot",
        lambda *_args, **_kwargs: calls.append("cache"),
    )
    monkeypatch.setattr(
        "widgets.weather_runtime.OpenMeteoProvider",
        lambda *_args, **_kwargs: calls.append("provider"),
    )

    owner, _consumer = _service()

    assert calls == []
    assert owner.get_cached_data() is None
    assert owner.runtime_generation == 0


def test_weather_startup_cache_load_runs_on_io_then_commits_on_gui(
    tmp_path,
    monkeypatch,
) -> None:
    from core.weather_preparation import load_weather_startup_snapshot as real_loader

    widget_cache = tmp_path / "weather_widget_cache.json"
    widget_cache.write_text(
        json.dumps(
            {
                "location": "London",
                "temperature": 18.5,
                "condition": "Clear sky",
                "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
                "humidity": 44.0,
                "precipitation_probability": 5.0,
                "windspeed": 11.0,
                "weather_code": 0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("widgets.weather_runtime._CACHE_FILE", widget_cache)
    manager = _QueuedIoManager()
    owner, consumer = _service(location="  london  ", manager=manager)
    main_thread_id = threading.get_ident()
    loader_threads: list[int] = []
    queued_ui = []
    schedule_threads: list[int] = []

    def _load(*args, **kwargs):
        loader_threads.append(threading.get_ident())
        return real_loader(*args, **kwargs)

    monkeypatch.setattr("widgets.weather_runtime.load_weather_startup_snapshot", _load)
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.run_on_ui_thread",
        lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs)),
    )
    monkeypatch.setattr(
        owner,
        "schedule_refresh_cycle",
        lambda: schedule_threads.append(threading.get_ident()),
    )

    assert owner.start() is True
    assert [task.category for task in manager.tasks] == ["weather_startup_cache"]
    worker = threading.Thread(target=_run_queued_io_task, args=(manager.tasks.pop(),))
    worker.start()
    worker.join()

    assert loader_threads[0] != main_thread_id
    assert consumer.states == []
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)

    assert schedule_threads == [main_thread_id]
    assert consumer.states[-1][0]["temperature"] == 18.5
    assert consumer.states[-1][1] is True
    assert owner.get_cached_data()["weather_code"] == 0
    assert owner._cache_time is not None


def test_weather_startup_cache_miss_can_request_immediate_refresh(monkeypatch) -> None:
    manager = _QueuedIoManager()
    owner, _consumer = _service(manager=manager)
    calls: list[str] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.run_on_ui_thread",
        lambda callback, *args, **kwargs: callback(*args, **kwargs),
    )
    monkeypatch.setattr(owner, "fetch_weather", lambda: calls.append("fetch"))
    monkeypatch.setattr(owner, "schedule_refresh_cycle", lambda: calls.append("schedule"))

    assert owner.start(immediate_refresh_on_miss=True) is True
    _run_queued_io_task(manager.tasks.pop())

    assert calls == ["fetch", "schedule"]


def test_weather_startup_snapshot_prefers_matching_provider_cache(tmp_path, caplog) -> None:
    from core.weather_preparation import load_weather_startup_snapshot

    caplog.set_level("INFO")
    widget_cache = tmp_path / "weather_widget_cache.json"
    provider_cache = tmp_path / "open_meteo_cache.json"
    widget_cache.write_text(
        json.dumps(
            {
                "location": "Paris",
                "temperature": 18.5,
                "condition": "Clear sky",
                "timestamp": datetime.now().isoformat(),
            }
        ),
        encoding="utf-8",
    )
    provider_cache.write_text(
        json.dumps(
            {
                "London": {
                    "location": "London",
                    "temperature": 9.0,
                    "condition": "Overcast",
                    "humidity": 55.0,
                    "_cached_at": datetime.now().timestamp() - 3600,
                }
            }
        ),
        encoding="utf-8",
    )

    snapshot = load_weather_startup_snapshot(
        "London",
        widget_cache_path_override=widget_cache,
        provider_cache_path_override=provider_cache,
    )

    assert snapshot.source == "provider"
    assert snapshot.stale is True
    assert snapshot.sample is not None
    assert snapshot.sample.location == "London"
    assert snapshot.sample.temperature == 9.0
    assert "Ignoring persisted widget cache for location=Paris" in caplog.text


def test_weather_location_change_rejects_late_startup_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    widget_cache = tmp_path / "weather_widget_cache.json"
    widget_cache.write_text(
        json.dumps(
            {
                "location": "London",
                "temperature": 18.5,
                "condition": "Clear sky",
                "timestamp": datetime.now().isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("widgets.weather_runtime._CACHE_FILE", widget_cache)
    manager = _QueuedIoManager()
    owner, consumer = _service(manager=manager)
    queued_ui = []
    scheduled: list[bool] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.run_on_ui_thread",
        lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs)),
    )
    monkeypatch.setattr(owner, "schedule_refresh_cycle", lambda: scheduled.append(True))

    owner.start()
    _run_queued_io_task(manager.tasks.pop())
    owner.set_location("Paris")
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)

    assert owner.get_cached_data() is None
    assert consumer.states == []
    assert scheduled == []


def test_weather_fetch_accepts_only_latest_request_and_persists_off_gui(
    tmp_path,
    monkeypatch,
) -> None:
    from core.weather_preparation import PreparedWeatherFetch, prepare_weather_sample
    from widgets.weather_runtime import _normalize_weather_location_key

    cache_path = tmp_path / "weather_widget_cache.json"
    monkeypatch.setattr("widgets.weather_runtime._CACHE_FILE", cache_path)
    manager = _QueuedIoManager()
    owner, consumer = _service(manager=manager)
    owner._running = True
    consumer.pending_first_show = False

    owner.fetch_weather()
    owner.fetch_weather()
    assert [task.category for task in manager.tasks] == ["weather_fetch", "weather_fetch"]
    latest_request_id = owner._fetch_request_id
    location_key = _normalize_weather_location_key("London")
    older = prepare_weather_sample(
        {"location": "London", "temperature": 10, "condition": "Rain"},
        fallback_location="London",
        observed_at=datetime.now() - timedelta(seconds=5),
    )
    newer = prepare_weather_sample(
        {"location": "London", "temperature": 20, "condition": "Clear"},
        fallback_location="London",
        observed_at=datetime.now(),
    )

    owner.commit_weather_fetch(
        latest_request_id - 1,
        location_key,
        PreparedWeatherFetch(older, persist_provider=True),
    )
    assert owner.get_cached_data() is None
    owner.commit_weather_fetch(
        latest_request_id,
        location_key,
        PreparedWeatherFetch(newer, persist_provider=True),
    )

    assert owner.get_cached_data()["temperature"] == 20.0
    assert consumer.states[-1][0]["condition"] == "Clear"
    persist_tasks = [task for task in manager.tasks if task.category == "weather_cache_persist"]
    assert len(persist_tasks) == 1
    worker = threading.Thread(target=_run_queued_io_task, args=(persist_tasks[0],))
    worker.start()
    worker.join()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["temperature"] == 20.0
    provider_payload = json.loads(
        (tmp_path / "open_meteo_cache.json").read_text(encoding="utf-8")
    )
    assert provider_payload["London"]["temperature"] == 20.0


def test_weather_location_b_rejects_late_location_a_provider_result() -> None:
    from core.weather_preparation import PreparedWeatherFetch, prepare_weather_sample
    from widgets.weather_runtime import _normalize_weather_location_key

    manager = _QueuedIoManager()
    owner, consumer = _service(manager=manager)
    owner._running = True
    consumer.pending_first_show = False
    owner.fetch_weather()
    request_a = owner._fetch_request_id
    owner.set_location("Paris")
    owner._running = True
    owner.fetch_weather()
    request_b = owner._fetch_request_id
    sample_a = prepare_weather_sample(
        {"location": "London", "temperature": 11, "condition": "Rain"},
        fallback_location="London",
    )
    sample_b = prepare_weather_sample(
        {"location": "Paris", "temperature": 24, "condition": "Clear"},
        fallback_location="Paris",
    )

    owner.commit_weather_fetch(
        request_a,
        _normalize_weather_location_key("London"),
        PreparedWeatherFetch(sample_a, persist_provider=False),
    )
    assert owner.get_cached_data() is None
    owner.commit_weather_fetch(
        request_b,
        _normalize_weather_location_key("Paris"),
        PreparedWeatherFetch(sample_b, persist_provider=False),
    )

    assert owner.get_cached_data()["location"] == "Paris"
    assert owner.get_cached_data()["temperature"] == 24.0


def test_weather_fetch_defers_provider_cache_until_gui_accepts_request(
    tmp_path,
    monkeypatch,
) -> None:
    provider_path = tmp_path / "open_meteo_cache.json"
    widget_path = tmp_path / "weather_widget_cache.json"
    manager = _QueuedIoManager()
    owner, consumer = _service(manager=manager)
    owner._running = True
    consumer.pending_first_show = False
    queued_ui = []
    constructor_flags: list[bool] = []

    class _Provider:
        def __init__(self, timeout=10, *, persist_results=True):
            constructor_flags.append(persist_results)
            self.last_result_was_network = True

        def get_current_weather(self, location):
            return {"location": location, "temperature": 21, "condition": "Clear"}

    monkeypatch.setattr("widgets.weather_runtime.OpenMeteoProvider", _Provider)
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.run_on_ui_thread",
        lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs)),
    )

    owner.fetch_weather()
    _run_queued_io_task(manager.tasks.pop())
    assert constructor_flags == [False]
    assert provider_path.exists() is False
    assert widget_path.exists() is False

    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)
    assert provider_path.exists() is False
    persist_task = manager.tasks.pop()
    assert persist_task.category == "weather_cache_persist"
    _run_queued_io_task(persist_task)
    provider_payload = json.loads(provider_path.read_text(encoding="utf-8"))
    assert provider_payload["London"]["temperature"] == 21.0


def test_weather_persistence_is_atomic_and_newest_wins(tmp_path) -> None:
    from core.weather_preparation import prepare_weather_sample, write_weather_widget_cache

    cache_path = tmp_path / "weather_widget_cache.json"
    newer = prepare_weather_sample(
        {"location": "Paris", "temperature": 24, "condition": "Clear"},
        fallback_location="Paris",
        observed_at=datetime.now(),
    )
    older = prepare_weather_sample(
        {"location": "London", "temperature": 8, "condition": "Rain"},
        fallback_location="London",
        observed_at=newer.observed_at - timedelta(minutes=1),
    )

    assert write_weather_widget_cache(newer, cache_path_override=cache_path) is True
    assert write_weather_widget_cache(older, cache_path_override=cache_path) is False
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["location"] == "Paris"
    assert payload["temperature"] == 24.0
    assert list(tmp_path.glob("*.tmp")) == []


def test_weather_provider_cache_merge_preserves_locations(tmp_path) -> None:
    from core.weather_preparation import prepare_weather_sample, write_weather_provider_cache

    provider_path = tmp_path / "weather.json"
    now = datetime.now()
    london = prepare_weather_sample(
        {"location": "London", "temperature": 18, "condition": "Rain"},
        fallback_location="London",
        observed_at=now,
    )
    paris = prepare_weather_sample(
        {"location": "Paris", "temperature": 24, "condition": "Clear"},
        fallback_location="Paris",
        observed_at=now + timedelta(seconds=1),
    )
    older_london = prepare_weather_sample(
        {"location": "London", "temperature": 5, "condition": "Snow"},
        fallback_location="London",
        observed_at=now - timedelta(minutes=1),
    )

    assert write_weather_provider_cache(london, cache_path_override=provider_path) is True
    assert write_weather_provider_cache(paris, cache_path_override=provider_path) is True
    assert write_weather_provider_cache(older_london, cache_path_override=provider_path) is False
    payload = json.loads(provider_path.read_text(encoding="utf-8"))
    assert set(payload) == {"London", "Paris"}
    assert payload["London"]["temperature"] == 18.0


def test_weather_stop_and_retire_fence_late_results() -> None:
    from core.weather_preparation import PreparedWeatherFetch, prepare_weather_sample
    from widgets.weather_runtime import _normalize_weather_location_key

    manager = _QueuedIoManager()
    owner, consumer = _service(manager=manager)
    owner._running = True
    owner.fetch_weather()
    request_id = owner._fetch_request_id
    sample = prepare_weather_sample(
        {"location": "London", "temperature": 18, "condition": "Cloudy"},
        fallback_location="London",
    )

    owner.stop()
    owner.commit_weather_fetch(
        request_id,
        _normalize_weather_location_key("London"),
        PreparedWeatherFetch(sample, persist_provider=True),
    )
    assert owner.get_cached_data() is None
    assert consumer.states == []

    owner.retire()
    owner.retire()
    assert owner.is_retired() is True
    assert owner._consumer() is None
    assert owner._update_timer_handle is None


def test_weather_fetch_without_thread_manager_never_constructs_provider(monkeypatch) -> None:
    owner, _consumer = _service()
    calls: list[bool] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.OpenMeteoProvider",
        lambda *_args, **_kwargs: calls.append(True),
    )

    owner.fetch_weather()

    assert calls == []


def test_weather_retry_is_single_and_fenced_by_stop(monkeypatch) -> None:
    owner, _consumer = _service()
    owner._running = True
    scheduled = []
    fetched: list[bool] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.single_shot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )
    monkeypatch.setattr(owner, "fetch_weather", lambda: fetched.append(True))

    owner.schedule_retry(delay_ms=60_000)
    owner.schedule_retry(delay_ms=60_000)
    assert len(scheduled) == 1
    owner.stop()
    scheduled[0][1]()

    assert fetched == []
    assert owner._retry_pending is False


def test_weather_refresh_cycle_uses_startup_and_jitter_policy(monkeypatch) -> None:
    owner, _consumer = _service()
    owner._running = True
    single_shots = []
    timer_calls = []

    class _Handle:
        def __init__(self):
            self._timer = object()
            self.stopped = False

        def stop(self):
            self.stopped = True
            self._timer = None

    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.single_shot",
        lambda delay, callback: single_shots.append((delay, callback)),
    )
    monkeypatch.setattr("widgets.weather_runtime.random.randint", lambda _a, _b: 60_000)
    monkeypatch.setattr(
        "widgets.weather_runtime.create_overlay_timer",
        lambda target, interval, callback, description="": (
            timer_calls.append((target, interval, callback, description)) or _Handle()
        ),
    )

    owner.schedule_refresh_cycle()

    assert single_shots[0][0] == 30_000
    assert timer_calls == [
        (
            owner,
            31 * 60 * 1000,
            owner._on_periodic_refresh_timeout,
            "Weather runtime refresh",
        )
    ]
    first_handle = owner._update_timer_handle
    first_callback = single_shots[0][1]
    fetched: list[bool] = []
    monkeypatch.setattr(owner, "fetch_weather", lambda: fetched.append(True))
    owner.schedule_refresh_cycle()
    first_callback()

    assert first_handle.stopped is True
    assert owner._update_timer_handle is not first_handle
    assert fetched == []


def test_weather_refresh_cycle_skips_startup_when_cache_is_fresh(monkeypatch) -> None:
    owner, _consumer = _service()
    owner._running = True
    owner._cache_time = datetime.now()
    single_shots = []
    timer_calls = []

    class _Handle:
        _timer = object()

        def stop(self):
            self._timer = None

    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.single_shot",
        lambda delay, callback: single_shots.append((delay, callback)),
    )
    monkeypatch.setattr("widgets.weather_runtime.random.randint", lambda _a, _b: 0)
    monkeypatch.setattr(
        "widgets.weather_runtime.create_overlay_timer",
        lambda target, interval, callback, description="": (
            timer_calls.append((target, interval, callback, description)) or _Handle()
        ),
    )

    owner.schedule_refresh_cycle()

    assert single_shots == []
    assert timer_calls[0][1] == 30 * 60 * 1000


def test_weather_refresh_cycle_disables_only_automatic_updates(monkeypatch) -> None:
    owner, _consumer = _service()
    owner._running = True
    single_shots = []
    timer_calls = []
    manual_calls: list[bool] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.automatic_service_updates_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "widgets.weather_runtime.ThreadManager.single_shot",
        lambda delay, callback: single_shots.append((delay, callback)),
    )
    monkeypatch.setattr(
        "widgets.weather_runtime.create_overlay_timer",
        lambda *args, **kwargs: timer_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(owner, "_fetch_via_thread_manager", lambda *_args: manual_calls.append(True))
    owner.set_thread_manager(object())

    owner.schedule_refresh_cycle()
    owner.fetch_weather()

    assert single_shots == []
    assert timer_calls == []
    assert manual_calls == [True]
