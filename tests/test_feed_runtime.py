from __future__ import annotations

import time
from types import SimpleNamespace

from core.feeds.config import CustomFeedConfig
from core.feeds.models import (
    FeedDocument,
    FeedHealth,
    FeedItem,
    FeedRefreshResult,
    FeedSnapshot,
)
from widgets import feed_runtime
from widgets.feed_runtime import FeedRuntimeConfig, FeedRuntimeLease


class _Manager:
    def __init__(self):
        self.submissions = 0

    def submit_io_task(self, work, *, callback, **_kwargs):
        self.submissions += 1
        try:
            result = work()
            callback(SimpleNamespace(success=True, result=result))
        except Exception as exc:
            callback(SimpleNamespace(success=False, result=None, error=exc))


class _Source:
    def __init__(self, result):
        self.result = result
        self.cache_calls = 0
        self.refresh_calls = 0

    def load_cached(self):
        self.cache_calls += 1
        return self.result

    def refresh(self, *, force=False):
        self.refresh_calls += 1
        return self.result


class _Consumer:
    def __init__(self, generation=7):
        self._runtime_generation = generation
        self.accepted = []
        self.alive = True

    def is_feed_consumer_alive(self):
        return self.alive

    def on_feed_runtime_result(self, result, *, from_cache):
        self.accepted.append((result, from_cache))


def _config(widget_id="feeds_custom_1", *, refresh_minutes=15):
    return CustomFeedConfig.from_mapping(
        widget_id,
        {
            "enabled": True,
            "name": "Goblin",
            "feed_url": "https://example.test/feed.xml",
            "refresh_minutes": refresh_minutes,
        },
    )


def _result(now=None):
    now = time.time() if now is None else float(now)
    snapshot = FeedSnapshot(
        FeedDocument(
            title="Goblin Feed",
            home_url="https://example.test/",
            format="rss",
            items=(FeedItem("1", "One", "https://example.test/one"),),
        ),
        fetched_at=now,
    )
    return FeedRefreshResult(
        "available",
        snapshot,
        FeedHealth(last_checked_at=now, last_success_at=now),
        changed=False,
    )


def setup_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def teardown_function():
    feed_runtime.reset_shared_feed_runtime_for_tests()


def test_leases_share_one_generation_owner_and_cache_first_source(monkeypatch):
    manager = _Manager()
    result = _result()
    source = _Source(result)
    def source_for(_owner, state):
        state.source = source
        return source
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    scheduled = []

    def schedule(delay_ms, callback):
        scheduled.append((delay_ms, callback))
        return lambda: None

    config = FeedRuntimeConfig.from_custom(_config())
    first = FeedRuntimeLease(config=config, generation=99, manager=manager, ui_dispatch=lambda fn: fn(), schedule=schedule, task_priority=0)
    second = FeedRuntimeLease(config=config, generation=99, manager=manager, ui_dispatch=lambda fn: fn(), schedule=schedule, task_priority=0)
    c1, c2 = _Consumer(99), _Consumer(99)
    first.attach_consumer(c1)
    second.attach_consumer(c2)

    assert first.start() is True
    assert second.start() is True
    assert feed_runtime.shared_feed_owner_count() == 1
    # First lease loads disk state; the second joins retained accepted state and
    # must not start a duplicate cache/network transaction.
    assert source.cache_calls == 1
    assert source.refresh_calls == 0
    assert manager.submissions == 1
    assert c1.accepted and c1.accepted[-1][1] is True
    assert c2.accepted and c2.accepted[-1][0] == result
    assert scheduled  # one shared earliest-due deadline, not one timer per lease

    first.retire()
    assert feed_runtime.shared_feed_owner_count() == 1
    second.retire()
    assert feed_runtime.shared_feed_owner_count() == 0


def test_manual_refresh_is_generation_owned_and_bounded_to_one_inflight(monkeypatch):
    manager = _Manager()
    source = _Source(_result())
    def source_for(_owner, state):
        state.source = source
        return source
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config()),
        generation=3,
        manager=manager,
        ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None),
        task_priority=0,
    )
    consumer = _Consumer(3)
    lease.attach_consumer(consumer)
    assert lease.start()
    assert lease.request_refresh() is True
    assert source.refresh_calls == 1
    lease.retire()
    assert lease.request_refresh() is False


def test_detach_consumer_severs_callback_without_becoming_second_lifetime_owner(monkeypatch):
    manager = _Manager()
    source = _Source(_result())
    def source_for(_owner, state):
        state.source = source
        return source
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config()),
        generation=5,
        manager=manager,
        ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None),
        task_priority=0,
    )
    consumer = _Consumer(5)
    lease.attach_consumer(consumer)
    assert lease.start()
    lease.detach_consumer(consumer)
    assert lease.is_running() is True
    lease.retire()
    assert lease.is_retired() is True
    assert feed_runtime.shared_feed_owner_count() == 0


def test_empty_cache_immediately_performs_one_network_refresh(monkeypatch):
    manager = _Manager()
    fresh = _result()

    class EmptyThenFresh:
        def __init__(self):
            self.cache_calls = 0
            self.refresh_calls = 0
        def load_cached(self):
            self.cache_calls += 1
            return FeedRefreshResult("unavailable", None, FeedHealth(), failure="no_cache")
        def refresh(self, *, force=False):
            self.refresh_calls += 1
            return fresh

    source = EmptyThenFresh()
    def source_for(_owner, state):
        state.source = source
        return source
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config()),
        generation=8,
        manager=manager,
        ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None),
        task_priority=0,
    )
    consumer = _Consumer(8)
    lease.attach_consumer(consumer)
    assert lease.start()
    assert source.cache_calls == 1
    assert source.refresh_calls == 1
    assert manager.submissions == 2
    assert consumer.accepted[-1][0] == fresh
    assert consumer.accepted[-1][1] is False
    lease.retire()


def test_shared_source_cadence_recomputes_when_faster_lease_retires(monkeypatch):
    manager = _Manager()
    result = _result()
    source = _Source(result)

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    schedule = lambda _ms, _fn: (lambda: None)

    slower = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config(refresh_minutes=30)),
        generation=21, manager=manager, ui_dispatch=lambda fn: fn(),
        schedule=schedule, task_priority=0,
    )
    faster = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config(refresh_minutes=5)),
        generation=21, manager=manager, ui_dispatch=lambda fn: fn(),
        schedule=schedule, task_priority=0,
    )
    slower.attach_consumer(_Consumer(21))
    faster.attach_consumer(_Consumer(21))

    assert slower.start()
    assert faster.start()
    owner = slower._owner
    assert owner is faster._owner
    state = next(iter(owner._states.values()))
    assert state.refresh_minutes == 5
    fast_due = state.due_at

    faster.retire()
    assert state.refresh_minutes == 30
    assert state.due_at > fast_due

    slower.retire()


def test_inactive_last_consumer_releases_http_source_without_waiting_for_generation_teardown(monkeypatch):
    manager = _Manager()
    result = _result()

    class Transport:
        def __init__(self):
            self.closed = 0
        def close(self):
            self.closed += 1

    source = _Source(result)
    source.transport = Transport()

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config()),
        generation=31, manager=manager, ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None), task_priority=0,
    )
    consumer = _Consumer(31)
    lease.attach_consumer(consumer)
    assert lease.start()
    owner = lease._owner
    state = next(iter(owner._states.values()))
    assert state.source is source

    lease.stop()
    assert state.source is None
    assert source.transport.closed == 1

    lease.retire()


def test_same_endpoint_different_custom_slots_share_one_source_state(monkeypatch):
    manager = _Manager()
    result = _result()
    source = _Source(result)

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    schedule = lambda _ms, _fn: (lambda: None)
    one = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(CustomFeedConfig.from_mapping(
            "feeds_custom_1", {"enabled": True, "name": "One", "feed_url": "https://example.test/feed.xml", "refresh_minutes": 15}
        )), generation=44, manager=manager, ui_dispatch=lambda fn: fn(), schedule=schedule, task_priority=0,
    )
    two = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(CustomFeedConfig.from_mapping(
            "feeds_custom_2", {"enabled": True, "name": "Two", "feed_url": "https://example.test/feed.xml", "refresh_minutes": 30}
        )), generation=44, manager=manager, ui_dispatch=lambda fn: fn(), schedule=schedule, task_priority=0,
    )
    one.attach_consumer(_Consumer(44))
    two.attach_consumer(_Consumer(44))
    assert one.start() and two.start()
    owner = one._owner
    assert owner is two._owner
    assert len(owner._states) == 1
    assert manager.submissions == 1
    one.retire(); two.retire()


def test_cache_only_source_does_not_construct_http_transport():
    """Fresh-cache admission must not wake requests/session machinery."""
    from core.feeds.models import FeedCacheRecord
    from core.feeds.normalization import endpoint_fingerprint
    from core.feeds.source import FeedSource

    class Cache:
        def read(self, _key):
            return record
        def write(self, _key, _record):
            raise AssertionError("cache-only load must not write")

    made = []
    spec = _config().source_spec()
    # Match the synthetic record to the real spec identity.
    record = FeedCacheRecord(
        source_id=spec.source_id,
        endpoint_fingerprint=endpoint_fingerprint(spec.url),
        snapshot=_result().snapshot,
        health=_result().health,
    )
    source = FeedSource(
        spec,
        cache=Cache(),
        transport_factory=lambda: made.append(object()) or (_ for _ in ()).throw(AssertionError("transport constructed")),
    )
    result = source.load_cached()
    assert result.snapshot is not None
    assert source.transport is None
    assert made == []


def test_feed_config_import_is_http_and_parser_neutral_in_clean_process():
    """Schema/config discovery must not wake requests or feedparser."""
    import subprocess
    import sys

    script = (
        "import sys; import core.feeds.config; import core.feeds.source; "
        "assert 'requests' not in sys.modules; "
        "assert 'feedparser' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=str(__import__('pathlib').Path(__import__('core').__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_reactivation_reuses_retained_result_without_reloading_cache(monkeypatch):
    manager = _Manager()
    result = _result()
    source = _Source(result)

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(_config()),
        generation=52, manager=manager, ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None), task_priority=0,
    )
    consumer = _Consumer(52)
    lease.attach_consumer(consumer)
    assert lease.start()
    assert source.cache_calls == 1
    assert manager.submissions == 1

    lease.stop()
    owner = lease._owner
    state = next(iter(owner._states.values()))
    # The source/HTTP state is gone while the immutable accepted result stays.
    assert state.source is None
    assert state.last_result == result

    assert lease.start()
    assert source.cache_calls == 1
    assert manager.submissions == 1
    assert consumer.accepted[-1][0] == result
    lease.retire()


def test_feed_product_action_rejects_non_http_schemes_before_opener():
    from core.widget_product_actions import dispatch_feed_url_product_action

    opened = []
    exited = []
    for target in (
        "magnet:?xt=urn:btih:abc",
        "file:///tmp/feed",
        "javascript:alert(1)",
        "https:///missing-host",
    ):
        assert dispatch_feed_url_product_action(
            target,
            opener=lambda url: opened.append(url) or True,
            request_saver_exit=lambda: exited.append(True),
            interactive_build=False,
        ) is False
    assert opened == []
    assert exited == []

    assert dispatch_feed_url_product_action(
        "https://example.test/item",
        opener=lambda url: opened.append(url) or True,
        request_saver_exit=lambda: exited.append(True),
        interactive_build=False,
    ) is True
    assert opened == ["https://example.test/item"]
    assert exited == [True]

class _DeferredManager:
    """Deterministic worker admission; a specific endpoint may retire in flight."""

    def __init__(self):
        self.tasks = []

    def submit_io_task(self, work, *, callback, **_kwargs):
        self.tasks.append((work, callback))

    def finish(self, index):
        work, callback = self.tasks[index]
        try:
            callback(SimpleNamespace(success=True, result=work()))
        except Exception as exc:
            callback(SimpleNamespace(success=False, error=exc))


def _lease_for_url(manager, *, slot, url, generation=81):
    config = CustomFeedConfig.from_mapping(slot, {
        "enabled": True, "name": "Probe", "feed_url": url,
        "refresh_minutes": 15,
    })
    lease = FeedRuntimeLease(
        config=FeedRuntimeConfig.from_custom(config), generation=generation,
        manager=manager, ui_dispatch=lambda fn: fn(),
        schedule=lambda _ms, _fn: (lambda: None), task_priority=0,
    )
    consumer = _Consumer(generation)
    lease.attach_consumer(consumer)
    return lease, consumer


def test_retiring_one_endpoint_cancels_only_its_queued_work_and_prunes_state(monkeypatch):
    manager = _DeferredManager()
    sources = {}

    def source_for(_owner, state):
        source = sources.setdefault(state.spec.cache_key, _Source(_result()))
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    first, abandoned = _lease_for_url(
        manager, slot="feeds_custom_1", url="https://example.test/one.xml")
    second, retained = _lease_for_url(
        manager, slot="feeds_custom_2", url="https://example.test/two.xml")
    assert first.start() and second.start()
    owner = first._owner
    first_key, second_key = first.config.source_spec.cache_key, second.config.source_spec.cache_key
    assert owner is second._owner and len(manager.tasks) == 2
    first.retire()
    assert first_key in owner._states and second_key in owner._states
    assert owner._states[first_key].work_cancel.is_set()
    assert not owner._states[second_key].work_cancel.is_set()
    manager.finish(0)
    assert first_key not in owner._states
    assert not abandoned.accepted
    manager.finish(1)
    assert len(retained.accepted) == 1
    assert sources[second_key].cache_calls == 1
    assert feed_runtime.shared_feed_owner_count() == 1
    second.retire()
    assert feed_runtime.shared_feed_owner_count() == 0


def test_shared_endpoint_is_cancelled_only_after_its_last_active_lease(monkeypatch):
    manager = _DeferredManager()
    source = _Source(_result())

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    first, first_consumer = _lease_for_url(
        manager, slot="feeds_custom_1", url="https://example.test/shared.xml")
    second, second_consumer = _lease_for_url(
        manager, slot="feeds_custom_2", url="https://example.test/shared.xml")
    assert first.start() and second.start() and len(manager.tasks) == 1
    state = next(iter(first._owner._states.values()))
    first.stop()
    assert not state.work_cancel.is_set()
    manager.finish(0)
    assert not first_consumer.accepted and len(second_consumer.accepted) == 1
    assert source.cache_calls == 1
    first.retire()
    second.retire()


def test_cancelled_inflight_source_never_publishes_on_reactivation(monkeypatch):
    manager = _DeferredManager()
    source = _Source(_result())

    def source_for(_owner, state):
        state.source = source
        return source

    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for", source_for)
    lease, consumer = _lease_for_url(
        manager, slot="feeds_custom_1", url="https://example.test/reuse.xml")
    assert lease.start() and len(manager.tasks) == 1
    lease.stop()
    assert lease.start()
    # The old work was canceled; reattachment must wait for its completion,
    # then issue a new cache-first admission, not publish the abandoned result.
    assert len(manager.tasks) == 1
    manager.finish(0)
    assert len(manager.tasks) == 2 and not consumer.accepted
    manager.finish(1)
    assert source.cache_calls == 1 and len(consumer.accepted) == 1
    lease.retire()
